"""General utilities for building NCBI URLs (BLAST and Taxonomy)."""

from src.utils.config import Config


def build_blast_url(taxon: str, taxid: int, config: Config) -> str:
    query_seq = config.read_query_fasta(
        index=config.get_query_ix(config.query_dir)
    ).seq
    return (
        'https://blast.ncbi.nlm.nih.gov/Blast.cgi?PROGRAM=blastn'
        '&PAGE_TYPE=BlastSearch&'
        f'EQ_MENU={taxon.replace(" ", "%20")}'
        f'%20(taxid:{taxid})'
        f'&QUERY={query_seq}'
    )


def build_taxonomy_url(taxid: str) -> str:
    return (
        'https://www.ncbi.nlm.nih.gov'
        '/Taxonomy/Browser/wwwtax.cgi?mode=Info&id='
        f'{taxid}'
    ) if taxid else None
