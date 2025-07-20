import unittest
from pathlib import Path
from unittest.mock import call, mock_open, patch, MagicMock
import p2_extract_taxonomy
from src.taxonomy import extract

TAXONKIT_STDOUT = Path(__file__).parent / "test-data/taxonkit.stdout"
ACCESSION_TAXIDS = {
    'ACC1': '1529436',
    'ACC2': '2711157',
    'ACC3': '1529435',
}
INPUT_CSV_DATA = """ACC1,1529436
ACC2,2711157
ACC3,1529435
"""
TAXONOMIES_RETURN_VALUE = {
    '1529436': {
        "superkingdom": "Eukaryota",
        "kingdom": "Metazoa",
        "phylum": "Echinodermata",
        "class": "Crinoidea",
        "order": "Comatulida",
        "family": "Comatulidae",
        "genus": "Anneissia",
        "species": "Anneissia japonica"
    },
    '2711157': {
        "superkingdom": "Eukaryota",
        "kingdom": "Metazoa",
        "phylum": "Echinodermata",
        "class": "Crinoidea",
        "order": "Comatulida",
        "family": "Comatulidae",
        "genus": "Anneissia",
        "species": "Anneissia pinguis"
    },
    '1529435': {
        "superkingdom": "Eukaryota",
        "kingdom": "Metazoa",
        "phylum": "Echinodermata",
        "class": "Crinoidea",
        "order": "Comatulida",
        "family": "Comatulidae",
        "genus": "Anneissia",
        "species": "Anneissia bennetti"
    }
}
EXPECTED_WRITE_CALLS = [
    call('w'),
    call().__enter__(),
    call().write(
        'accession,taxid,domain,superkingdom,kingdom,phylum,class,order'
        ',family,genus,species\r\n'),
    call().write(
        'ACC1,1529436,,Eukaryota,Metazoa,Echinodermata,Crinoidea'
        ',Comatulida,Comatulidae,Anneissia,Anneissia japonica\r\n'),
    call().write(
        'ACC2,2711157,,Eukaryota,Metazoa,Echinodermata,Crinoidea'
        ',Comatulida,Comatulidae,Anneissia,Anneissia pinguis\r\n'),
    call().write(
        'ACC3,1529435,,Eukaryota,Metazoa,Echinodermata,Crinoidea'
        ',Comatulida,Comatulidae,Anneissia,Anneissia bennetti\r\n'),
    call().__exit__(None, None, None),
]


def mock_subprocess_run(args, **kwargs):
    if args[0] == "taxonkit":
        retval = MagicMock()
        retval.stdout = TAXONKIT_STDOUT.read_text()
        retval.returncode = 0
        return retval
    raise NotImplementedError(
        f"Command not implemented for mock: {args[0]}")


class TestNcbiTaxonomy(unittest.TestCase):
    @patch('subprocess.run')
    def test_it_can_extract_taxonomic_data_for_accessions(self, mock_run):
        mock_run.side_effect = mock_subprocess_run
        taxids = sorted(ACCESSION_TAXIDS.values())
        output = extract.taxonomies(taxids)
        self.assertEqual(output, TAXONOMIES_RETURN_VALUE)

    @patch('subprocess.run')
    @patch("p2_extract_taxonomy._parse_args")
    @patch("p2_extract_taxonomy.config")
    def test_main(self, mock_config, mock_parse_args, mock_run):
        """Test main() using mock_open for both read and write operations."""
        mock_run.side_effect = mock_subprocess_run

        # Mock file handling using mock_open
        mock_input_open = mock_open(read_data=INPUT_CSV_DATA)
        mock_output_open = mock_open()

        # Mock arguments with taxids_csv and output_csv
        mock_args = unittest.mock.MagicMock()
        mock_args.taxdb_path = "mock_taxdb"
        mock_args.taxids_csv.open = mock_input_open
        mock_parse_args.return_value = mock_args

        mock_output_dir = unittest.mock.MagicMock()
        mock_output_dir.__truediv__.return_value = mock_output_dir
        mock_output_dir.exists.return_value = True
        mock_output_dir.open = mock_output_open
        mock_config.output_dir = mock_output_dir

        m = mock_open(read_data=INPUT_CSV_DATA)
        with patch("builtins.open", m):
            p2_extract_taxonomy.main()

        # Verify that the expected write calls happened
        mock_output_open.assert_has_calls(
            EXPECTED_WRITE_CALLS,
            any_order=True,
        )

call().write('accession,taxid,superkingdom,kingdom,phylum,class,order,family,genus,species\r\n'),
call().write('ACC1,1529436,Eukaryota,Metazoa,Echinodermata,Crinoidea,Comatulida,Comatulidae,Anneissia,Anneissia japonica\r\n'),
call().write('ACC2,2711157,Eukaryota,Metazoa,Echinodermata,Crinoidea,Comatulida,Comatulidae,Anneissia,Anneissia pinguis\r\n'),
call().write('ACC3,1529435,Eukaryota,Metazoa,Echinodermata,Crinoidea,Comatulida,Comatulidae,Anneissia,Anneissia bennetti\r\n')

call().write('accession,taxid,domain,superkingdom,kingdom,phylum,class,order,family,genus,species\r\n'),
call().write('ACC1,1529436,,Eukaryota,Metazoa,Echinodermata,Crinoidea,Comatulida,Comatulidae,Anneissia,Anneissia japonica\r\n'),
call().write('ACC2,2711157,,Eukaryota,Metazoa,Echinodermata,Crinoidea,Comatulida,Comatulidae,Anneissia,Anneissia pinguis\r\n'),
call().write('ACC3,1529435,,Eukaryota,Metazoa,Echinodermata,Crinoidea,Comatulida,Comatulidae,Anneissia,Anneissia bennetti\r\n')
