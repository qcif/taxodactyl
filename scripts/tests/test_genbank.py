import json
import os
import threading
import time
import unittest
from pathlib import Path
from queue import Queue
from unittest.mock import patch

from src.entrez.genbank import (
    GbRecordSource,
    fetch_gb_records,
    fetch_sources,
)
from src.utils import serialize
from src.utils.config import Config

config = Config()

RESPECT_RATE_LIMIT = 1
PERFORMANCE = 2
CONCURRENCY_TEST = RESPECT_RATE_LIMIT

DATA_DIR = Path(__file__).parent / 'test-data'
EXPECTED_RECORD_COUNT = 62401
EXPECT_RECORDS_JSON = DATA_DIR / 'genbank_expect_ids.json'
EXPECT_SINGLE_SOURCE_JSON = DATA_DIR / 'genbank_single_source.json'
EXPECT_MULTIPLE_SOURCES_JSON = DATA_DIR / 'genbank_multiple_sources.json'
ACCESSIONS_LIST_FILE = DATA_DIR / 'accessions.txt'

ACCESSION_1 = "NM_001126"
ACCESSION_2 = "HQ621368"
DATABASE = "nuccore"
SINGLE_ACCESSION = [ACCESSION_1]
MULTIPLE_ACCESSIONS = [ACCESSION_1, ACCESSION_2]
LOCUS = 'COI'
TAXID = "9606"
MOCK_ENTREZ_IDS = {
    "Count": 5,
    "IdList": [
        "ABC",
        "DEF",
        "GHI",
        "JKL",
        "MNO",
    ],
}
MAX_ACCESSIONS = 20  # Limit number of accessions to request
BATCH_SIZE = 10  # Number of accessions per request, in PERFORMANCE mode


class TestFetchRecords(unittest.TestCase):

    def setUp(self):
        for loc in config.allowed_loci:
            if LOCUS in loc:
                self.locus = loc.rename(LOCUS)
                break

    def test_fetch_gb_records_count(self):
        result = fetch_gb_records(self.locus, TAXID, True)
        self.assertGreaterEqual(result, EXPECTED_RECORD_COUNT)

    @patch("Bio.Entrez.read", return_value=MOCK_ENTREZ_IDS)
    def test_fetch_gb_records_ids(self, mock_read):
        result = fetch_gb_records(self.locus, TAXID, False)
        missing_ids = set(MOCK_ENTREZ_IDS['IdList']) - set(result)
        self.assertEqual(len(missing_ids), 0)

    def test_fetch_single_source(self):
        result = fetch_sources(SINGLE_ACCESSION)
        expected = EXPECT_SINGLE_SOURCE_JSON.read_text()
        observed = json.dumps(result, default=serialize)
        self.assertEqual(observed, expected)

    def test_fetch_multiple_source(self):
        result = fetch_sources(MULTIPLE_ACCESSIONS)
        expected = json.loads(EXPECT_MULTIPLE_SOURCES_JSON.read_text())
        observed = json.loads(json.dumps(result, default=serialize))
        self.assertEqual(observed, expected)

    @unittest.skipUnless(
        os.getenv("GENBANK_CONCURRENCY_TEST") == "1",
        "Skipping genbank concurrency test")
    def test_parallel_requests(self):
        """Test that parallel requests do not get blocked by the API."""
        def worker(accession):
            try:
                result = fetch_sources([accession])
                results_queue.put((accession, result))
            except Exception as e:
                results_queue.put((accession, str(e)))

        t0 = time.time()
        results_queue = Queue()
        threads = []
        accessions = [
            a.strip()
            for a in ACCESSIONS_LIST_FILE.read_text().splitlines()
            if a.strip()
        ]

        if CONCURRENCY_TEST == RESPECT_RATE_LIMIT:
            for acc in accessions[:MAX_ACCESSIONS]:
                t = threading.Thread(target=worker, args=(acc,))
                t.start()
                threads.append(t)

        elif CONCURRENCY_TEST == PERFORMANCE:
            for i in range(0, MAX_ACCESSIONS, BATCH_SIZE):
                acc = accessions[i:i + BATCH_SIZE]
                t = threading.Thread(target=worker, args=(','.join(acc),))
                t.start()
                threads.append(t)

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Collect results
        results = {}
        while not results_queue.empty():
            acc, result = results_queue.get()
            results.update(result)

        td = time.time() - t0  # use a breakpoint to check the time taken
        print("Time taken:", td)

        # Assert that all requests succeeded (i.e., no exceptions)
        for acc, result in results.items():
            self.assertIsInstance(
                result,
                GbRecordSource,
                f"Failed for {acc}: {result}")
            self.assertIn(
                acc,
                accessions,
                f"Returned accession not found in the query list: {acc}")
        self.assertEqual(len(results), MAX_ACCESSIONS)
