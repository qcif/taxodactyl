"""General utilities related to BLAST search."""

from src.utils.config import Config


def build_blast_url(taxon: str, taxid: int, config: Config) -> str:
    query_seq = config.read_query_fasta(
        index=config.get_query_ix(config.query_dir)
    ).seq
    return (
        'https://blast.ncbi.nlm.nih.gov/Blast.cgi?PROGRAM=blastn'
        '&PAGE_TYPE=BlastSearch&'
        f'EQ_MENU={taxon.replace(' ', '%20')}'
        f'%20(taxid:{taxid})'
        f'&DATABASE=core_nt&QUERY={query_seq}'
    )
