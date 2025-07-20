"""Provide an interface to the BOLD API for search and metadata retrieval.

API Docs: https://v4.boldsystems.org/index.php/resources/api
"""

import csv
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from xml.etree import ElementTree

from Bio import SeqIO
from Bio.Seq import Seq

import requests

from src.gbif.taxonomy import fetch_kingdom
from src.utils import errors
from src.utils.orient import orientate
from src.utils.throttle import ENDPOINTS, Throttle

logger = logging.getLogger(__name__)
BOLD_DATABASE = "COX1_SPECIES_PUBLIC"
ID_ENGINE_URL = "http://v4.boldsystems.org/index.php/Ids_xml"
FULL_DATA_URL = "http://v4.boldsystems.org/index.php/API_Public/combined"
SEQUENCE_DATA_URL = "http://v4.boldsystems.org/index.php/API_Public/sequence"
MIN_HTTP_CODE_ERROR = 400


class BoldSearch:
    """Fetch metadata for given taxa from the BOLD API."""
    def __init__(self, fasta_file: Path, db: str = BOLD_DATABASE):
        self.fasta_file = fasta_file
        raw_hits = self._bold_sequence_search(fasta_file, db)
        if not any(raw_hits.values()):
            logger.info("No hits from BOLD ID Engine for FASTA query.")
        self.hits = self._fetch_hit_metadata(raw_hits)
        self.hit_sequences = self._parse_sequences(self.hits)
        self.taxa = self._extract_taxa(self.hits)
        self.records = self._fetch_records(self.taxa)

    @property
    def taxon_count(self) -> dict[str, int]:
        """Return a count of records for each taxon."""
        taxa_counts = {}
        for record in self.records:
            taxon = record.get("species_name", "")
            taxa_counts[taxon] = taxa_counts.get(taxon, 0) + 1
        return taxa_counts

    @property
    def taxon_collectors(self) -> dict[str, list[str]]:
        """Return a dictionary of taxa and related collectors."""
        taxa_collectors = {}
        for record in self.records:
            taxon = record.get("species_name", "")
            collector = record.get("collectors", "")
            if taxon:
                if taxon not in taxa_collectors:
                    taxa_collectors[taxon] = set()
                if collector:
                    taxa_collectors[taxon].update(collector.split(","))
        return {
            k: list(v)
            for k, v in taxa_collectors.items()
        }

    @property
    def taxon_taxonomy(self) -> dict[str, dict[str, str]]:
        """Build a taxonomy dictionary."""
        taxonomy_dict = {}
        for record in self.records:
            species_name = record.get("species_name", "")
            if species_name:
                taxonomy_dict[species_name] = {
                    "phylum": record.get("phylum_name", ""),
                    "class": record.get("class_name", ""),
                    "order": record.get("order_name", ""),
                    "family": record.get("family_name", ""),
                    "genus": record.get("genus_name", ""),
                    "species": species_name,
                }
        return self._fetch_kingdoms(taxonomy_dict)

    def _read_sequence_from_fasta(
        self,
        fasta_file: Path,
    ) -> list[SeqIO.SeqRecord]:
        """Read sequence from fasta file."""
        sequences = []
        for record in SeqIO.parse(fasta_file, "fasta"):
            sequences.append(record)
        return sequences

    def _parse_bold_xml(self, xml_string):
        root = ElementTree.fromstring(xml_string.text)
        hits = []
        for match in root.findall("match"):
            similarity_str = match.find("similarity").text
            latitude_str = match.find(
                "specimen/collectionlocation/coord/lat").text
            longitude_str = match.find(
                "specimen/collectionlocation/coord/lon").text
            result = {
                "hit_id": match.find("ID").text,
                "sequence_description": (
                    match.find("sequencedescription").text
                ),
                "database": match.find("database").text,
                "citation": match.find("citation").text,
                "taxonomic_identification": (
                    match.find("taxonomicidentification").text
                ),
                "similarity": (
                    float(similarity_str) if similarity_str else None),
                "specimen": match.find("specimen").text,
                "url": match.find("specimen/url").text,
                "country": (
                    match.find("specimen/collectionlocation/country").text
                ),
                "latitude": float(latitude_str) if latitude_str else None,
                "longitude": (
                    float(longitude_str) if longitude_str else None),
            }
            hits.append(result)
        return hits

    def _bold_sequence_search(
        self,
        fasta_file: Path,
        db: str = BOLD_DATABASE,
    ) -> dict[str, list[dict[str, any]]]:
        """Submit a sequence search request to BOLD API.
        Attempt to orientate sequences before submission. For sequences which
        cannot be oriented, both forward and reverse sequences are submitted
        and the sequence which returns BOLD hits is used.
        """
        def submit_sequence(sequence, i, n_sequences: int):
            throttle = Throttle(ENDPOINTS.BOLD)
            logger.debug(
                f"Submitting sequence {i + 1}/{n_sequences}"
                f": {sequence.id}"
            )
            params = {
                "sequence": str(sequence.seq),
                "db": db
            }
            response = throttle.with_retry(
                requests.get,
                args=[ID_ENGINE_URL],
                kwargs={"params": params})
            response.raise_for_status()

            sequence_hits = self._parse_bold_xml(response)
            return sequence.id, sequence_hits

        hits = {}
        sequences = self._read_sequence_from_fasta(fasta_file)
        seqids = [seq.id for seq in sequences]
        n_sequences = len(sequences)
        if not os.getenv('SKIP_ORIENTATION'):
            sequences = orientate(sequences)
        logger.debug(
            f"Submitting {n_sequences} sequences to BOLD ID Engine..."
        )

        # If multiple seq IDs, only keep the one with hits
        # (the correct orientation)
        # Submit all sequences concurrently
        with ThreadPoolExecutor(max_workers=15) as executor:
            future_to_seq = {
                executor.submit(
                    submit_sequence,
                    sequence,
                    i,
                    n_sequences
                ): sequence
                for i, sequence in enumerate(sequences)
            }

            # Collect results as they complete
            for future in as_completed(future_to_seq):
                sequence = future_to_seq[future]
                sequence_id, sequence_hits = future.result()
                if (
                    sequence_id not in hits
                    or sequence_hits
                ):
                    hits[sequence_id] = {
                        'query_index': seqids.index(sequence_id),
                        'query_id': sequence_id,
                        'query_title': sequence.description,
                        'query_length': len(sequence.seq),
                        'query_frame': sequence.annotations.get(
                            "frame"
                        ),
                        'query_strand': (
                            '+'
                            if sequence.annotations.get(
                                "forward", True
                            )
                            else '-'
                        ),
                        'query_sequence': str(sequence.seq),
                        'query_orientation': (
                            'HMMSearch'
                            if sequence.annotations.get(
                                "oriented"
                            )
                            else 'BOLD ID Engine'
                        ),
                        'hits': sequence_hits,
                    }

            ordered_hits = {
                seq.id: hits[seq.id]
                for seq in sequences
            }

            return ordered_hits

    def _fetch_hit_metadata(self, hits) -> dict[str, list]:
        """Fetch metadata by calling BOLD public API with accessions."""
        def _fetch_batch(batch_ids):
            params = {
                "ids": "|".join(batch_ids),
                "format": "tsv",
            }
            throttle = Throttle(ENDPOINTS.BOLD)
            response = throttle.with_retry(
                requests.get,
                args=[FULL_DATA_URL],
                kwargs={"params": params},
            )
            if response.status_code >= MIN_HTTP_CODE_ERROR:
                response.raise_for_status()
            lines = response.text.splitlines()
            reader = csv.DictReader(lines, delimiter="\t")
            return {
                row.pop("processid"): row
                for row in reader
            }

        hit_record_ids = [
            hit["hit_id"]
            for query_hits in hits.values()
            for hit in query_hits['hits']
        ]
        logger.info(
            f"Fetching sequences for {len(hit_record_ids)} hit records..."
        )
        metadata = {}
        batch_size = 25

        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = []
            for i in range(0, len(hit_record_ids), batch_size):
                batch = hit_record_ids[i:i + batch_size]
                futures.append(executor.submit(_fetch_batch, batch))
            for future in as_completed(futures):
                metadata.update(future.result())

        hits_with_metadata = {
            query_title: {
                **query_hits,
                'hits': [
                    {
                        **hit,
                        **metadata.get(hit["hit_id"], {}),
                    }
                    for hit in query_hits['hits']
                ],
            }
            for query_title, query_hits in hits.items()
        }

        # Expand taxonomy fields
        for query_title, query_hits in hits_with_metadata.items():
            for i, hit in enumerate(query_hits['hits']):
                hit['species'] = hit.get("species_name", "")
                hit['taxonomy'] = {
                    "phylum": hit.get("phylum_name", ""),
                    "class": hit.get("class_name", ""),
                    "order": hit.get("order_name", ""),
                    "family": hit.get("family_name", ""),
                    "genus": hit.get("genus_name", ""),
                    "species": hit.get("species_name", ""),
                }
                hit['accession'] = hit.pop("genbank_accession", "")
                hit['identity'] = hit['similarity']
                # Remove redundant fields
                hit.pop("phylum_name", None)
                hit.pop("class_name", None)
                hit.pop("order_name", None)
                hit.pop("family_name", None)
                hit.pop("genus_name", None)
                hit.pop("species_name", None)

                hits_with_metadata[query_title]['hits'][i] = hit

        self.raw_hits = None

        return hits_with_metadata

    def _parse_sequences(
        self,
        hits: dict[str, list[dict]],
    ) -> dict[str, list[SeqIO.SeqRecord]]:
        """Parse sequences from hits into SeqRecord objects."""
        query_hits_sequences = {}
        for query_title, query_hits in hits.items():
            query_hits_sequences[query_title] = [
                SeqIO.SeqRecord(
                    Seq(hit.get("nucleotides", "").replace('-', '')),
                    id=hit['hit_id'],
                    description=hit['taxonomic_identification'],
                )
                for hit in query_hits['hits']
            ]
        return query_hits_sequences

    def _extract_taxa(
        self,
        query_results: dict[str, dict[str, list[dict]]],
    ) -> list[str]:
        """Extract taxa (taxonomic_identification)."""
        taxa = []
        for result in query_results.values():
            for hit in result['hits']:
                taxonomic_identification = hit.get("taxonomic_identification")
                if (
                    taxonomic_identification
                    and taxonomic_identification not in taxa
                ):
                    taxa.append(taxonomic_identification)
        return taxa

    def _fetch_records(self, taxa: list[str]) -> list[dict]:
        """Fetch records for taxa list by calling BOLD API."""
        records = []
        if not taxa:
            logger.info("No taxa to fetch BOLD metadata.")
            return records
        taxa_param = "|".join(taxa)
        params = {
            "taxon": taxa_param,
            "format": "tsv"
        }
        throttle = Throttle(ENDPOINTS.BOLD)
        response = throttle.with_retry(
                requests.get,
                args=[FULL_DATA_URL],
                kwargs={"params": params})
        if response.status_code <= MIN_HTTP_CODE_ERROR:
            lines = response.text.splitlines()
            if not lines:  # Check if 'lines' is empty
                msg = "Empty response received from BOLD API"
                logger.error(msg)
                errors.write(
                    errors.LOCATIONS.BOLD_TAXA,
                    msg,
                    context={"taxa": taxa},
                )
                return records

            headers = lines[0].split("\t")
            for line in lines[1:]:
                row = dict(zip(headers, line.split("\t")))
                records.append(row)
            logger.info(
                f"Records fetched successfully: {len(records)} records."
            )
        else:
            msg = (
                f"Error HTTP {response.status_code} from the BOLD API when"
                f" running ID Engine: {response.text}"
            )
            logger.error(msg)
            errors.write(
                errors.LOCATIONS.BOLD_TAXA,
                msg,
                exc=response.text,
                context={
                    "taxa": taxa,
                },
            )

        return records

    def _fetch_kingdoms(self, taxonomies: dict) -> dict:
        """Fetch correct taxonomic kingdom for each taxonomy."""
        phyla = {
            data['phylum']: None
            for data in taxonomies.values()
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
                    logger.error(
                        f"Error fetching kingdom for phylum {phylum}: {e}"
                    )

        return {
            taxon: {
                **data,
                "kingdom": phyla[data['phylum']] or 'NONE',
            }
            for taxon, data in taxonomies.items()
        }
