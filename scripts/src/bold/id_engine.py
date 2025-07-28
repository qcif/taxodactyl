"""Provide an interface to the BOLD API for search and metadata retrieval.

API Docs: https://v4.boldsystems.org/index.php/resources/api
"""

import logging
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from Bio import SeqIO
from Bio.Seq import Seq

import pandas as pd

from src.gbif.taxonomy import fetch_kingdom
from src.utils import config

config = config.Config()
logger = logging.getLogger(__name__)

BOLD_RECORD_BASE_URL = "https://portal.boldsystems.org/record/"
BOLDIGGER_OUTPUT_XLSX_PATTERN = (
    'boldigger3_data/queries_bold_results_part_*.xlsx')
BOLDIGGER_NO_MATCH_STR = 'no-match'
BOLDIGGER_OUTPUT_DIRNAME = 'boldigger3_output'


class BOLD_MODES:
    RAPID_SPECIES = 1
    GENUS_AND_SPECIES = 2
    EXHAUSTIVE = 3


class BoldSearch:
    """Fetch metadata for given taxa from the BOLD API."""
    def __init__(
        self,
        fasta_file: Path,
        database: int,
        mode: int,
        thresholds=None,
    ):
        self.fasta_file = fasta_file
        self.database = database
        self.mode = mode
        self.thresholds = thresholds
        self.query_sequences = self._read_fasta(fasta_file)
        self.query_seqids = [s.id for s in self.query_sequences]
        self.hits = self._bold_sequence_search()
        self.hit_sequences = self._parse_sequences()
        self._fetch_kingdoms()

    def _read_fasta(
        self,
        fasta_file: Path,
    ) -> list[SeqIO.SeqRecord]:
        """Read sequence from fasta file."""
        sequences = []
        for record in SeqIO.parse(fasta_file, "fasta"):
            sequences.append(record)
        return sequences

    def _parse_bold_xlsx(
        self,
        path: Path,
        results: dict = {},
    ) -> dict[str, list]:
        """Parse the results from BOLDigger3 XLSX output file.

        Optionally append results to an existing result dict.
        """
        df = pd.read_excel(path)

        for _, row in df.iterrows():
            query_id = row['id']
            query_seq = [
                s for s in self.query_sequences
                if s.id == query_id
            ][0]
            query_annotations = {
                'query_id': query_id,
                'query_title': query_seq.description,
                'query_index': self.query_seqids.index(query_id),
                'query_length': len(query_seq.seq),
                'query_sequence': query_seq.seq,
            }

            results[query_id] = results.get(query_id, {
                **query_annotations,
                'hits': [],
            })

            if row.get('phylum') == BOLDIGGER_NO_MATCH_STR:
                continue

            genus = row.get('genus', '')
            species = row.get('species', '')

            # Handle NaN values for genus and species
            if pd.isna(genus):
                genus = ''
            if pd.isna(species):
                species = ''

            taxonomic_identification = species if species else f"{genus} sp."
            process_id = row.get('processid')

            # Handle NaN process_id
            if pd.isna(process_id):
                process_id = ''
            else:
                process_id = str(process_id)

            hit = {
                "hit_id": process_id,
                "bin_uri": row.get('bin_uri'),
                "taxonomic_identification": taxonomic_identification,
                "identity": row.get('pct_identity'),
                "url": BOLD_RECORD_BASE_URL + process_id if process_id else '',
                "country": row.get('country/ocean'),
                "nucleotide": (
                    str(row.get('nuc', '')).replace('-', '')
                    if not pd.isna(row.get('nuc'))
                    else ''
                ),
                "identified_by": row.get('identified_by'),
                "phylum": row.get('phylum'),
                "class": row.get('class'),
                "order": row.get('order'),
                "family": row.get('family'),
                "genus": row.get('genus'),
                "species": row.get('species'),
            }
            results[query_id]['hits'].append(hit)

        return results

    def _bold_sequence_search(self) -> dict[str, list[dict[str, any]]]:
        """Submit a sequence search request using BOLDigger3."""
        wdir = config.output_dir / BOLDIGGER_OUTPUT_DIRNAME
        wdir.mkdir(parents=True, exist_ok=True)
        input_fasta_path = wdir / self.fasta_file.name
        input_fasta_path.write_text(self.fasta_file.read_text())
        args = [
            "boldigger3",
            "identify",
            str(input_fasta_path),
            "--db", str(self.database),
            "--mode", str(self.mode)
        ]
        if self.thresholds:
            args += ["--thresholds"] + [str(t) for t in self.thresholds]

        logger.info("Submitting query sequences to BOLD with BOLDigger3...")

        try:
            proc = subprocess.Popen(
                args,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # line-buffered
            )
            for line in proc.stdout:
                print(line, end='')

            proc.stdout.close()
            proc.wait()

        except Exception as exc:
            raise RuntimeError("Error running BOLDigger3") from exc

        results = {}
        for path in wdir.glob(BOLDIGGER_OUTPUT_XLSX_PATTERN):
            logger.info(f"Parsing BOLDigger results from {path}...")
            results = self._parse_bold_xlsx(path, results)
        if not results:
            raise RuntimeError(
                "No results found in BOLDigger outputs - this indicates a bug"
                " in the code, even for queries with no hits."
            )
        if config.BOLDIGGER_KEEP_OUTPUTS:
            logger.info(
                'BOLDIGGER_KEEP_OUTPUTS=true - BOLDigger outputs have been'
                f' saved to {wdir}')
        else:
            shutil.rmtree(wdir, ignore_errors=True)

        return results

    def _parse_sequences(self) -> list[SeqIO.SeqRecord]:
        """Parse sequences from hits into SeqRecord objects."""
        sequences = {}
        for seqid, hits in self.hits.items():
            sequences[seqid] = [
                SeqIO.SeqRecord(
                    Seq(hit["nucleotides"]),
                    id=hit['hit_id'],
                    description=hit['taxonomic_identification'],
                )
                for hit in hits
                if hit.get("nucleotides")
            ]

        return sequences

    def _fetch_kingdoms(self) -> dict:
        """Fetch correct taxonomic kingdom for each taxonomy."""
        phyla = {
            hit['phylum']: None
            for hits in self.hits.values()
            for hit in hits
        }

        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = {
                executor.submit(fetch_kingdom, phylum): phylum
                for phylum in phyla.keys()
            }
            for future in as_completed(futures):
                phylum = futures[future]
                try:
                    kingdom = future.result()
                    if kingdom:
                        phyla[phylum] = kingdom
                    else:
                        logger.warning(
                            f"Kingdom not found for phylum: {phylum}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Error fetching kingdom for phylum {phylum}: {e}"
                    )

        for query in self.hits:
            for hit in self.hits[query]:
                hit['kingdom'] = phyla[hit['phylum']]
