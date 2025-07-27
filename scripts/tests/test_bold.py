import unittest
from unittest.mock import MagicMock
from pathlib import Path
from Bio import SeqIO
from Bio.Seq import Seq

from src.bold.id_engine import BoldSearch, BOLDIGGER_NO_MATCH_STR


class TestBoldSearch(unittest.TestCase):
    """Test cases for BoldSearch class methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_path = Path(__file__).parent / "test-data/boldigger3_data/queries_bold_results_part_1.xlsx"
        self.fasta_path = Path(__file__).parent / "test-data/queries.fasta"
        
        # Read actual query sequences from FASTA file
        with open(self.fasta_path, "r") as fasta_file:
            self.query_sequences = list(SeqIO.parse(fasta_file, "fasta"))
        self.query_seqids = [seq.id for seq in self.query_sequences]
        
        # Create a minimal BoldSearch instance for testing
        self.bold_search = BoldSearch.__new__(BoldSearch)
        self.bold_search.query_sequences = self.query_sequences
        self.bold_search.query_seqids = self.query_seqids

    def test_parse_bold_xlsx_basic_functionality(self):
        """Test that _parse_bold_xlsx correctly parses the XLSX file."""
        results = self.bold_search._parse_bold_xlsx(self.test_data_path)
        
        # Check that results is a dictionary
        self.assertIsInstance(results, dict)
        
        # Check that we have results for our query sequence
        self.assertIn("LC438549.1", results)
        
        # Check query annotations are present
        query_result = results["LC438549.1"]
        self.assertEqual(query_result["query_id"], "LC438549.1")
        self.assertEqual(query_result["query_title"], "LC438549.1 Anneissia japonica mitochondrial COX1 mRNA for cytochrome c oxidase subunit 1, partial cds")
        self.assertEqual(query_result["query_index"], 0)
        self.assertEqual(query_result["query_length"], 602)
        # Check first 50 characters of sequence
        self.assertEqual(str(query_result["query_sequence"])[:50], "GGTAAAAAAAATGAGTTTTTGGCTTTTGCCTCCTTCTTTTCTTCTTTTAT")
        
        # Check that hits are present
        self.assertIn("hits", query_result)
        self.assertIsInstance(query_result["hits"], list)
        self.assertGreater(len(query_result["hits"]), 0)
        
        # Check that all FASTA sequence IDs are present in results
        expected_ids = {'LC438549.1', 'ON075825.1', 'PP466915.1', 'JQ585746.1', 'LC547004.1'}
        self.assertEqual(set(results.keys()), expected_ids)

    def test_parse_bold_xlsx_hit_structure(self):
        """Test that hits have the correct structure and required fields."""
        results = self.bold_search._parse_bold_xlsx(self.test_data_path)
        
        # Get the first hit for testing
        hits = results["LC438549.1"]["hits"]
        self.assertGreater(len(hits), 0)
        
        first_hit = hits[0]
        
        # Check required fields are present
        required_fields = [
            "hit_id", "bin_uri", "taxonomic_identification", "identity",
            "url", "country", "nucleotide", "identified_by", "phylum",
            "class", "order", "family", "genus", "species"
        ]
        
        for field in required_fields:
            self.assertIn(field, first_hit)
        
        # Check URL format
        self.assertTrue(first_hit["url"].startswith("https://portal.boldsystems.org/record/"))
        
        # Check nucleotide sequence has no dashes
        self.assertNotIn("-", first_hit["nucleotide"])

    def test_parse_bold_xlsx_taxonomic_identification(self):
        """Test taxonomic identification logic."""
        results = self.bold_search._parse_bold_xlsx(self.test_data_path)
        hits = results["LC438549.1"]["hits"]
        
        for hit in hits:
            taxonomic_id = hit["taxonomic_identification"]
            genus = hit["genus"]
            species = hit["species"]
            
            # Handle NaN values
            import pandas as pd
            species_is_valid = species and not pd.isna(species) and str(species).strip()
            genus_is_valid = genus and not pd.isna(genus) and str(genus).strip()
            
            if species_is_valid:
                # If species is present, taxonomic_identification should be the species
                self.assertEqual(taxonomic_id, species)
            elif genus_is_valid:
                # If no species but genus exists, should be "genus sp."
                self.assertEqual(taxonomic_id, f"{genus} sp.")
            else:
                # If neither species nor genus is valid, taxonomic_identification should be empty string or " sp."
                self.assertTrue(taxonomic_id in ["", " sp."])

    def test_parse_bold_xlsx_no_match_filtering(self):
        """Test that no-match entries are filtered out."""
        results = self.bold_search._parse_bold_xlsx(self.test_data_path)
        hits = results["LC438549.1"]["hits"]
        
        # Ensure no hits have 'no-match' as phylum
        for hit in hits:
            self.assertNotEqual(hit["phylum"], BOLDIGGER_NO_MATCH_STR)

    def test_parse_bold_xlsx_append_to_existing_results(self):
        """Test that results can be appended to existing results dictionary."""
        # Create initial results
        initial_results = {
            "existing_query": {
                "query_id": "existing_query",
                "hits": [{"existing": "hit"}]
            }
        }
        
        # Parse XLSX and append to existing results
        results = self.bold_search._parse_bold_xlsx(self.test_data_path, initial_results)
        
        # Check that existing results are preserved
        self.assertIn("existing_query", results)
        self.assertEqual(results["existing_query"]["hits"][0]["existing"], "hit")
        
        # Check that new results are added
        self.assertIn("LC438549.1", results)

    def test_parse_bold_xlsx_empty_results_dict(self):
        """Test parsing with an empty results dictionary."""
        results = self.bold_search._parse_bold_xlsx(self.test_data_path, {})
        
        self.assertIsInstance(results, dict)
        self.assertIn("LC438549.1", results)
        
    def test_parse_bold_xlsx_sequence_consistency(self):
        """Test that parsed results match the input FASTA sequences."""
        results = self.bold_search._parse_bold_xlsx(self.test_data_path)
        
        # Check that each sequence from FASTA matches the parsed result
        for i, seq_record in enumerate(self.query_sequences):
            seq_id = seq_record.id
            if seq_id in results:
                result = results[seq_id]
                self.assertEqual(result["query_id"], seq_id)
                self.assertEqual(result["query_title"], seq_record.description)
                self.assertEqual(result["query_index"], i)
                self.assertEqual(result["query_length"], len(seq_record.seq))
                self.assertEqual(str(result["query_sequence"]), str(seq_record.seq))


if __name__ == "__main__":
    unittest.main()