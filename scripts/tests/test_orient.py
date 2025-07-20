"""Test orientation of query sequences."""

import shutil
import unittest
from pathlib import Path

from Bio import SeqIO

from scripts.src.utils.orient import orientate

TEST_FASTA = Path(__file__).parent / "test-data" / "orient.fasta"
TEST_FASTA_FWD_INDEXES = (0, 4)
TEST_FASTA_REV_INDEXES = (1, 5)
TEST_FASTA_NO_COX1_INDEXES = (2, 3, 6)


class TestSequenceOrientation(unittest.TestCase):

    def setUp(self):
        """Set up test data."""
        if not shutil.which("hmmsearch"):
            self.skipTest("hmmsearch command not found in PATH")
        self.sequences = list(SeqIO.parse(TEST_FASTA, "fasta"))

    def test_orientate(self):
        """Test the orientate function."""
        oriented_sequences = orientate(self.sequences)

        # Should be two seqs for no-cox1 record
        self.assertEqual(len(oriented_sequences), 10)

        # Each sequence should have an "oriented" annotation
        for seq in oriented_sequences:
            self.assertIn("oriented", seq.annotations)
            self.assertTrue(seq.annotations["oriented"] in [True, False])

        # Confirm orientation of forward sequences
        for ix in TEST_FASTA_FWD_INDEXES:
            identifier = self.sequences[ix].id
            oriented = [s for s in oriented_sequences if s.id == identifier]
            self.assertEqual(len(oriented), 1)
            self.assertTrue(oriented[0].annotations["oriented"])
            self.assertTrue(oriented[0].annotations["forward"])

        # Confirm orientation of reverse sequences
        for ix in TEST_FASTA_REV_INDEXES:
            identifier = self.sequences[ix].id
            oriented = [s for s in oriented_sequences if s.id == identifier]
            self.assertEqual(len(oriented), 1)
            self.assertTrue(oriented[0].annotations["oriented"])
            self.assertFalse(oriented[0].annotations["forward"])

        for ix in TEST_FASTA_NO_COX1_INDEXES:
            identifier = self.sequences[ix].id
            oriented = [s for s in oriented_sequences if s.id == identifier]
            self.assertEqual(len(oriented), 2)
            fwd = oriented[0]
            rev = oriented[1]
            self.assertFalse(fwd.annotations["oriented"])
            self.assertFalse(rev.annotations["oriented"])
            self.assertFalse(fwd.annotations["reverse_complement"])
            self.assertTrue(rev.annotations["reverse_complement"])
