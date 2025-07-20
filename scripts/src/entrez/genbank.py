"""Use Entrez module from Biopython to fetch sequence data
from NCBI/Genbank."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree as ET

from Bio import Entrez

from src.utils.config import Config
from src.utils.locus import Locus
from src.utils.throttle import ENDPOINTS, Throttle

config = Config()
logger = logging.getLogger(__name__)

DEBUG_REQUESTS = True
EFETCH_BATCH_SIZE = 10
AUTOMATED_ANNOTATION_TAG = '##Genome-Annotation-Data-START##'

Entrez.email = config.USER_EMAIL
if config.NCBI_API_KEY:
    logger.info(f"Using NCBI API key: {config.NCBI_API_KEY[:5]}*********")
    Entrez.api_key = config.NCBI_API_KEY


class GbRecordSource:
    """A source of sequence record.

    Can be either a publication, set of authors or automated annotation.
    Instances can be compared with the `shares_publication_with` method, which
    determines if two sources share a publication source. This is not done by
    exact matching of publication metadata, but by establishing a match
    between a single metadata field (in order of preference: title, authors,
    journal). If the source is automated (e.g. automated genome annotation),
    it will only match with other automated sources.
    """

    def __init__(self, accession: str):
        self.accession = accession
        self.is_automated = False
        self._publications = []

    def __hash__(self) -> int:
        return hash(str(self._publications))

    def __bool__(self) -> bool:
        return len(self._publications) > 0

    @property
    def publications(self) -> list[dict]:
        return [
            {
                'authors': authors,
                'title': title,
                'journal': journal,
            }
            for authors, title, journal in self._publications
        ]

    def to_json(self) -> dict:
        return {
            'accession': self.accession,
            'is_automated': self.is_automated,
            'publications': self.publications,
        }

    def add_publication(
        self,
        authors: list[str] = None,
        title: str = None,
        journal: str = None,
    ):
        self._publications.append((
            authors,
            title,
            journal,
        ))

    def matches(self, other) -> bool:
        """Return True if other has a publication source that matches self."""
        if not isinstance(other, GbRecordSource):
            return False
        self_publications = self.get_publication_repr()
        other_publications = other.get_publication_repr()
        has_shared_source = self_publications == other_publications
        has_shared_publication = any(
            pub for pub in self_publications
            if pub in other_publications
        )
        if has_shared_publication or has_shared_source:
            return True
        return False

    def get_publication_repr(self) -> list[str]:
        """Return string representations of publications that can be used to
        assert fuzzy uniqueness against another (case-insensitive).
        """
        def get_repr(p):
            if authors := p.get('authors'):
                # Remove punctuation and spaces to allow for fuzzy matching
                # between records
                return ', '.join(
                    a.replace('.', '')
                    .replace(',', '')
                    .replace(' ', '')
                    .lower()
                    for a in authors
                )
            if title := p.get('title', ''):
                # Don't include "direct submission" titles - not useful
                if len(title) > 20 or 'direct submission' not in title.lower():
                    return title.lower()
            if journal := p.get('journal'):
                return journal.lower()

        if self.is_automated:
            return []
        return [
            get_repr(p)
            for p in self.publications
        ]


def fetch_entrez(
    endpoint=Entrez.efetch,
    db='nuccore',
    truncate_metadata=False,
    **kwargs,
) -> str:
    """Fetch data from NCBI Entrez database.
    Throttle requests to avoid rate limits and retry on failure.
    If truncate_metadata is set, the response will be truncated before sequence
    data begins to avoid downloading large amounts of surplus data.
    """
    def read(handle):
        if endpoint == Entrez.efetch:
            if truncate_metadata:
                data = b""
                for line in handle:
                    if (
                        b'<GBSeq_feature-table>' in line
                        or b'<GBSeq_sequence>' in line
                    ):
                        break
                    data += line
                data += b"\n</GBSeq></GBSet>"
                return data
            return handle.read()
        return Entrez.read(handle)

    Entrez.local_cache = config.entrez_cache_dir
    handle = None
    kwargs.update({
        "db": db,
    })
    throttle = Throttle(ENDPOINTS.ENTREZ)
    handle = throttle.with_retry(endpoint, kwargs=kwargs)
    data = read(handle)
    handle.close()
    return data


def fetch_fasta(identifier, **kwargs):
    return fetch_entrez(
        ids=identifier,
        rettype="fasta",
        retmode="text",
        **kwargs,
    )


def fetch_sources(accessions: list, **kwargs) -> dict[str, GbRecordSource]:
    def fetch_and_parse(accession: str):
        """Fetch Genbank metadata for the given accession."""
        logger.debug(f"Fetching Genbank metadata for accession {accession}")
        metadata_xml = fetch_entrez(
            id=accession,
            rettype="gb",
            retmode="xml",
            truncate_metadata=True,
            **kwargs,
        ).decode('utf-8')
        return parse_metadata(metadata_xml)

    accession_sources = {}
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [
            executor.submit(
                fetch_and_parse,
                acc,
            )
            for acc in accessions
        ]
        for future in as_completed(futures):
            sources = future.result()
            accession_sources.update(sources)

    missing_accessions = set(accessions) - set(accession_sources.keys())
    if missing_accessions:
        logger.warning("No data was returned for the"
                       " following accessions. They cannot be included in"
                       " source diversity analysis:"
                       f" {missing_accessions}")
        for accession in missing_accessions:
            accession_sources[accession] = GbRecordSource(accession)
            # TODO: error.write here?

    return accession_sources


def parse_metadata(xml_str: str) -> dict[str, GbRecordSource]:
    root = ET.fromstring(xml_str)
    records = {}
    for record in root.findall('.//GBSeq'):
        accession = getattr(
            record.find('GBSeq_primary-accession'), 'text', None)
        source = GbRecordSource(accession)
        for ref in record.findall('.//GBReference'):
            authors = [
                x.text for x in ref.findall('.//GBAuthor')
            ]
            title = getattr(ref.find('GBReference_title'), 'text', None)
            journal = getattr(ref.find('GBReference_journal'), 'text', None)
            source.add_publication(
                authors=authors,
                title=title,
                journal=journal,
            )
        if AUTOMATED_ANNOTATION_TAG in ET.tostring(record).decode('utf-8'):
            source.is_automated = True
        records[accession] = source
    return records


def fetch_gb_records(
    locus: Locus,
    taxid: int,
    count: bool = False,
) -> list[dict]:
    '''Find matching GenBank records.

    If count, returns a count of matching records, otherwise returns a list
    of matching accessions IDs.
    '''
    query = f'txid{taxid}[Organism])'
    if locus:
        query += f' AND ({locus.genbank_query_str})'
    max_results = 1 if count else 100
    logger.debug(f"Submitting Entrez query: <<{query}>>")
    results = fetch_entrez(
        endpoint=Entrez.esearch,
        term=query,
        retmax=max_results,
    )
    if count:
        return int(results["Count"])
    return results["IdList"]


if __name__ == '__main__':
    from pathlib import Path
    accessions = Path(
        '../tests/test-data/accessions.txt').read_text().splitlines()
    sources = fetch_sources(accessions[:20])
    print(f"Fetched sources for {len(sources)} accessions.")
