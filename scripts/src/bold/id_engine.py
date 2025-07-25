"""Provide an interface to the BOLD API for search and metadata retrieval.

API Docs: https://v4.boldsystems.org/index.php/resources/api
"""

import logging
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from Bio import SeqIO
from Bio.Seq import Seq

import pandas as pd

from src.gbif.taxonomy import fetch_kingdom
from src.utils.orient import SeqAnnotation, orientate

logger = logging.getLogger(__name__)

BOLD_RECORD_BASE_URL = "https://portal.boldsystems.org/record/"
BOLDIGGER_OUTPUT_XLSX_PATTERN = (
    'boldigger3_data/queries_bold_results_part_*.xlsx')
BOLDIGGER_NO_MATCH_STR = 'no-match'


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
        self.fasta_file = self._orientate(fasta_file)
        self.database = database
        self.mode = mode
        self.thresholds = thresholds
        self.hits = self._bold_sequence_search()
        self.hit_sequences = self._parse_sequences()
        self._fetch_kingdoms()

    def _orientate(self, fasta_file: Path) -> Path:
        """Orientate the sequences in the FASTA file."""
        sequences = self._read_fasta(fasta_file)
        self.oriented_sequences = orientate(sequences)
        out_path = fasta_file.with_suffix(".oriented.fasta")
        SeqIO.write(self.oriented_sequences, out_path, "fasta")
        return out_path

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
            raw_id = row['id']
            annotation = SeqAnnotation.from_identifier(raw_id)
            query_id = annotation.seqid
            seq = [
                s for s in self.oriented_sequences
                if s.id == query_id
            ][0]
            query_annotations = {
                'query_id': query_id,
                'query_title': seq.description,
                'query_index': annotation.index,
                'query_length': len(seq.seq),
                'query_sequence': seq.seq,
                'query_strand': annotation.strand,
                'query_orientation': annotation.orientation_method,
            }

            results[query_id] = results.get('query_id', {
                **query_annotations,
                'hits': [],
            })

            if row.get('phylum') == BOLDIGGER_NO_MATCH_STR:
                continue

            if (
                results[query_id]['hits']
                and results[query_id]['query_strand'] !=
                    query_annotations['query_strand']
            ):
                logger.warning(
                    'BOLD hits were returned for both query sequence'
                    ' orientations. Hits will only be collected from the (+)'
                    ' orientation.')
                continue

            genus = row.get('genus', '')
            species = row.get('species', '')
            taxonomic_identification = species if species else f"{genus} sp."
            process_id = row.get('processid')
            hit = {
                "hit_id": process_id,
                "bin_uri": row.get('bin_uri'),
                "taxonomic_identification": taxonomic_identification,
                "identity": row.get('pct_identity'),
                "url": BOLD_RECORD_BASE_URL + process_id,
                "country": row.get('country/ocean'),
                "nucleotide": row.get('nuc').replace('-', ''),
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
        wdir = tempfile.TemporaryDirectory()
        command = [
            "boldigger3", "identify", str(self.fasta_file),
            "--db", str(self.database),
            "--mode", str(self.mode)
        ]
        if self.thresholds:
            command += ["--thresholds"] + [str(t) for t in self.thresholds]

        try:
            subprocess.run(
                command,
                cwd=wdir.name,
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception as exc:
            raise RuntimeError("Error running BOLDigger3") from exc

        results = {}
        for path in wdir.glob(BOLDIGGER_OUTPUT_XLSX_PATTERN):
            if not path.is_file():
                continue
            logger.info(f"Parsing BOLDigger results from {path}...")
            results = self._parse_bold_xlsx(path, results)
        wdir.cleanup()

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
