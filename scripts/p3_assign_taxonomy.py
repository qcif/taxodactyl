"""Run logic for pipeline phase 1-2.

- Attempt species ID from BLAST results.json (flag 1)
- Detect Taxa of Interest (flag 2)

Taxa of Interest output has the following CSV fields:

Taxon of interest: The provided TOI that matched a candidate species
Match rank: The taxonomic rank of the match (TOI rank may be above species)
Match taxon: The taxon that matched the TOI
Match species: The species of the candidate match
Match accession: The NCBI accession of the candidate match

"""

import argparse
import csv
import json
import logging
from pathlib import Path


from Bio import SeqIO

from src.utils import deduplicate, existing_path
from src.utils.config import Config
from src.utils.flags import FLAGS, Flag

logging.getLogger('matplotlib').setLevel(logging.WARNING)
import matplotlib.pyplot as plt  # noqa:E402

logger = logging.getLogger(__name__)
config = Config()

CANDIDATE_CSV_HEADER = [
    "species",
    "taxid",
    "accession",
    "hit_subject",
    "identity",
    "query_coverage",
    "alignment_length",
    "e_value",
    "bitscore",
]
CANDIDATE_CSV_HEADER_BOLD = [
    "species",
    "hit_id",
    "accession",
    "sequence_description",
    "similarity",
    "bin_uri",
    "url",
]


def main():
    args = _parse_args()
    config.configure(args.output_dir, query_dir=args.query_dir)
    result = config.read_hits_json(args.query_dir)
    if args.bold:
        filtered_hits = result['hits']
        candidate_hits, candidate_hits_strict = _filter_hits_bold(
            filtered_hits)
    else:
        (
            filtered_hits,
            candidate_hits,
            candidate_hits_strict,
        ) = _filter_hits(result['hits'])
    candidate_species = _assign_species_id(
        args.query_dir,
        filtered_hits,
        candidate_hits,
        candidate_hits_strict,
        bold=args.bold,
    )
    _detect_taxa_of_interest(candidate_species, args.query_dir)


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "query_dir", type=existing_path, help="Path to query output directory")
    parser.add_argument(
        "--output_dir",
        type=existing_path,
        default=config.output_dir,
        help=f"Path to output directory. Defaults to {config.output_dir}.")
    parser.add_argument(
        "--bold",
        action="store_true",
        help="Outputs are from BOLD query.")
    return parser.parse_args()


def _filter_hits(hits):
    taxonomies = config.read_taxonomy_file()
    filtered_hits = [
        hit for hit in hits
        if (
            hit["alignment_length"] >= config.CRITERIA.ALIGNMENT_MIN_NT
            or hit["query_coverage"]
            >= config.CRITERIA.ALIGNMENT_MIN_Q_COVERAGE
        )
    ]
    for hit in filtered_hits:
        tax = taxonomies.get(hit["accession"])
        if tax:
            hit['taxonomy'] = tax
            hit["species"] = tax.get('species')
            hit['taxid'] = tax.get('taxid')
        else:
            hit['taxonomy'] = None
            hit["species"] = None
            hit['taxid'] = None
            logger.warning(
                f"Taxonomy record not found for {hit['accession']} -"
                " this hit could not be included in the candidate"
                " species list.")
    candidate_hits = [
        hit for hit in filtered_hits
        if hit["identity"] >= config.CRITERIA.ALIGNMENT_MIN_IDENTITY
    ]
    candidate_hits_strict = [
        hit for hit in candidate_hits
        if hit["identity"] >= config.CRITERIA.ALIGNMENT_MIN_IDENTITY_STRICT
    ]
    return filtered_hits, candidate_hits, candidate_hits_strict


def _filter_hits_bold(hits):
    candidate_hits = [
        hit for hit in hits
        if hit["similarity"] >= config.CRITERIA.ALIGNMENT_MIN_IDENTITY
    ]
    candidate_hits_strict = [
        hit for hit in candidate_hits
        if hit["similarity"] >= config.CRITERIA.ALIGNMENT_MIN_IDENTITY_STRICT
    ]
    return candidate_hits, candidate_hits_strict


def _assign_species_id(
    query_dir,
    filtered_hits,
    candidate_hits,
    candidate_hits_strict,
    bold=False,
):
    """Attempt species ID from BLAST/BOLD hits.json data."""
    def _get_counts(hits):
        """Get counts of hits and species."""
        return {
            'hits': len(hits),
            'species': len(deduplicate(
                [hit['species'] for hit in hits if hit['species']],
                key=lambda x: x.lower(),
            )),
        }

    def _get_median_bs_class(median_identity, top_identity):
        """Get the median identity class based on the top identity."""
        identity_threshold = (
            config.CRITERIA.ALIGNMENT_MIN_IDENTITY_STRICT
            if top_identity >= config.CRITERIA.ALIGNMENT_MIN_IDENTITY_STRICT
            else config.CRITERIA.ALIGNMENT_MIN_IDENTITY
        )
        if median_identity >= identity_threshold:
            return "success"
        elif (
            median_identity
            >= identity_threshold
            * config.CRITERIA.MEDIAN_IDENTITY_WARNING_FACTOR
        ):
            return "warning"
        else:
            return "danger"

    query_ix = config.get_query_ix(query_dir)
    candidate_species = deduplicate([
        hit for hit in candidate_hits
    ], key=lambda x: x.get("species"))
    candidate_species_strict = deduplicate([
        hit for hit in candidate_hits_strict
    ], key=lambda x: x.get("species"))

    # Add hit count for each candidate species
    for species in candidate_species:
        species["hit_count"] = sum(
            1 for hit in filtered_hits
            if hit["species"] == species["species"]
        )
    for species in candidate_species_strict:
        species["hit_count"] = sum(
            1 for hit in filtered_hits
            if hit["species"] == species["species"]
        )

    selected_species = candidate_species_strict or candidate_species
    selected_species_names = [s['species'] for s in selected_species]
    selected_hits = candidate_hits_strict or candidate_hits
    selected_hit_ids = [hit['hit_id'] for hit in selected_hits]
    selected_species_hits = [
        hit for hit in filtered_hits
        if hit['species'] in selected_species_names
    ]
    for hit in selected_species_hits:
        hit['is_candidate_hit'] = (
            True
            if hit['hit_id'] in selected_hit_ids
            else False
        )

    for hit in selected_species:
        hit_identities = [
            h['identity'] for h in selected_species_hits
            if h['species'] == hit['species']
        ]
        hit['median_identity'] = sorted(hit_identities)[
            len(hit_identities) // 2
        ]
        hit['median_bs_class'] = _get_median_bs_class(
            hit['median_identity'],
            hit['identity'],
        )

    moderate_match_ids = [
        hit['hit_id'] for hit in candidate_hits
    ]
    strong_match_ids = [
        hit['hit_id'] for hit in candidate_hits_strict
    ]
    no_match_hits = [
        hit for hit in filtered_hits
        if hit['hit_id'] not in moderate_match_ids
    ]
    moderate_hits = [
        hit for hit in candidate_hits
        if hit['hit_id'] not in strong_match_ids
    ]
    strong_hits = candidate_hits_strict

    hit_counts = {
        'filtered': _get_counts(no_match_hits),
        'moderate': _get_counts(moderate_hits),
        'strong': _get_counts(strong_hits),
    }

    _write_candidate_flags(
        query_dir,
        candidate_species_strict,
        candidate_species,
    )
    _write_candidates(
        query_dir,
        hit_counts,
        selected_species,
        selected_species_hits,
        bold=bold,
    )
    if len(selected_species) > config.CRITERIA.MAX_CANDIDATES_FOR_ANALYSIS:
        _write_boxplot(query_dir, selected_species_hits, bold)
    taxonomic_id = _write_taxonomic_id(query_dir, candidate_species_strict)
    _write_pmi_match(taxonomic_id, query_ix, query_dir)
    return selected_species


def _get_accessions_for_phylogeny(
    phylo_hits: list[dict],
    id_key: str,
    identity_key: str,
) -> list[str]:
    """Remove surplus sequences if there are too many per species.
    Sample hits in a systematic manner (by identity) to ensure a sample
    that is representative of sequence diversity.
    """
    def _systematic_sample(seq, n, key=None):
        """Return `n` elements spaced as evenly as possible through `seq`."""
        data = sorted(seq, key=key)
        N = len(data)
        if n <= 0:
            return []
        if n >= N:
            return data[:]               # every item
        if n == 1:
            return [data[(N - 1) // 2]]  # middle element

        step = (N - 1) / (n - 1)        # ideal distance between picks
        idx = [round(i * step) for i in range(n - 1)] + [N - 1]
        return [data[i] for i in idx]

    accessions = []
    max_hits = config.CRITERIA.PHYLOGENY_MAX_HITS_PER_SPECIES
    phylo_species = {
        hit['species'] for hit in phylo_hits
    }
    hits_by_species = {
        species: [
            hit for hit in phylo_hits
            if hit['species'] == species
        ]
        for species in phylo_species
    }
    for hits in hits_by_species.values():
        if len(hits) > max_hits:
            # Take a sample representative of sequence diversity
            accessions += [
                hit[id_key]
                for hit in _systematic_sample(
                    hits,
                    max_hits,
                    key=lambda x: x[identity_key],
                )
            ]
        else:
            accessions += [hit[id_key] for hit in hits]
    return accessions


def _write_taxonomic_id(query_dir, candidate_species_strict):
    if len(candidate_species_strict) != 1:
        logger.info(
            f"Query {query_dir} - not writing {config.TAXONOMY_ID_CSV}:"
            " no taxonomic identification could be made"
            f" ({len(candidate_species_strict)} candidates found).")
    else:
        src = query_dir / config.CANDIDATES_CSV
        dest = query_dir / config.TAXONOMY_ID_CSV
        dest.write_text(src.read_text())
        logger.info(f"Writing taxonomic ID to {config.TAXONOMY_ID_CSV}")
        return candidate_species_strict[0]


def _write_candidate_flags(query_dir, candidates_strict, candidates):
    if len(candidates_strict) == 1:
        value = FLAGS.A
    elif len(candidates_strict) > 1 and len(candidates_strict) < 4:
        value = FLAGS.B
    elif len(candidates_strict) >= 4:
        value = FLAGS.C
    elif len(candidates):
        value = FLAGS.D
    else:
        value = FLAGS.E
    Flag.write(query_dir, FLAGS.POSITIVE_ID, value)


def _write_candidates(
    query_dir: Path,
    hit_counts: dict[str, dict[str, int]],
    candidate_species: list[str],
    candidate_species_hits: list[dict],
    bold: bool = False,
):
    """Write candidates hits and species to file."""
    _write_candidates_json(
        query_dir,
        hit_counts,
        candidate_species_hits,
        candidate_species,
    )
    _write_candidates_csv(query_dir, candidate_species_hits, bold)
    _write_candidates_fasta(query_dir, candidate_species_hits, bold)
    _write_candidates_count(query_dir, candidate_species)


def _write_candidates_json(query_dir, hit_counts, hits, species):
    path = query_dir / config.CANDIDATES_JSON
    with path.open("w") as f:
        json.dump({
            "hits": hits,
            "species": species,
            "hit_counts": hit_counts,
        }, f, indent=2)
    logger.info(f"Written candidate hits/species to {path}")


def _write_candidates_csv(query_dir, hits, bold=False):
    header = CANDIDATE_CSV_HEADER_BOLD if bold else CANDIDATE_CSV_HEADER
    path = query_dir / config.CANDIDATES_CSV
    with path.open("w") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for hit in hits:
            writer.writerow([
                hit.get(key, "")
                for key in header
            ])
    logger.info(f"Written candidate species to {path}")


def _write_candidates_fasta(query_dir, hits, bold=False):
    """Write FASTA sequences for each candidate species to file.

    Writes two FASTA files:
    - candidates.fasta: Contains all candidate sequences
    - phylogeny.fasta: Contains a subset of candidate sequences for phylogeny
    """
    id_key = "hit_id" if bold else "accession"
    identity_key = "similarity" if bold else "identity"
    path = query_dir / config.CANDIDATES_FASTA
    phylo_path = query_dir / config.PHYLOGENY_FASTA
    fastas = config.read_hits_fasta(query_dir)
    accessions = [
        hit[id_key] for hit in hits
    ]
    phylogeny_hits = []
    for hit in sorted(
        hits,
        key=lambda x: x[identity_key]
    ):
        if len(phylogeny_hits) > config.CRITERIA.PHYLOGENY_MIN_HIT_SEQUENCES:
            break
        phylogeny_hits.append(hit)

    phylogeny_accessions = _get_accessions_for_phylogeny(
        phylogeny_hits,
        id_key,
        identity_key,
    )

    candidate_fastas = [
        fasta for fasta in fastas
        if fasta.id in accessions
    ]
    phylogeny_fastas = [
        fasta for fasta in fastas
        if fasta.id in phylogeny_accessions
    ]
    with open(path, "w") as f:
        SeqIO.write(candidate_fastas, f, "fasta")
    logger.info(f"Written candidate FASTA to {path}")
    with open(phylo_path, "w") as f:
        SeqIO.write(phylogeny_fastas, f, "fasta")
    logger.info(f"Written phylogeny FASTA to {phylo_path}")


def _write_candidates_count(query_dir, candidate_species):
    path = query_dir / config.CANDIDATES_COUNT_FILE
    count = len(candidate_species)
    with path.open("w") as f:
        f.write(str(count))
    logger.info(f"Written candidate count [{count}] to {path}")


def _write_pmi_match(taxonomic_identity, query_ix, query_dir):
    """Write PMI match as a flag."""
    if taxonomic_identity:
        match = [
            (rank, taxon)
            for rank, taxon in taxonomic_identity["taxonomy"].items()
            if taxon.lower() == config.get_pmi_for_query(query_ix).lower()
        ]
        logger.info("Writing PMI match flag")
        Flag.write(
            query_dir,
            FLAGS.PMI,
            FLAGS.A if match else FLAGS.B,
        )
        if match:
            path = query_dir / config.PMI_MATCH_CSV
            with path.open('w') as f:
                f.write(','.join(('rank', 'taxon')))
                f.write(','.join(match[0]))
    else:
        logger.info("No taxonomic ID - PMI flag 7NA written.")
        Flag.write(
            query_dir,
            FLAGS.PMI,
            FLAGS.NA,
        )


def _write_boxplot(query_dir, hits, bold=False):
    title = 'Similarity to query (%)' if bold else 'Identity to query (%)'
    identity_key = 'similarity' if bold else 'identity'
    genera = {}
    for hit in hits:
        genus = hit['species'].split(' ')[0] if hit['species'] else 'No genus'
        if genus not in genera:
            genera[genus] = []
        genera[genus].append(hit[identity_key] * 100)
    labels = []
    identities = []
    for genus, values in genera.items():
        labels.append(genus)
        identities.append(values)
    plt.figure(figsize=(12, 3))
    plt.boxplot(identities, labels=labels, patch_artist=True)
    if len(genera) > 5:
        plt.xticks(rotation=80)
    plt.xlabel('Genus', fontsize=14)
    plt.ylabel(title, fontsize=14)
    boxplot_image_path = query_dir / config.BOXPLOT_IMG_FILENAME
    plt.savefig(boxplot_image_path, bbox_inches='tight', dpi=150)
    plt.close()
    logger.info(f"Written boxplot PNG to {boxplot_image_path}")


def _detect_taxa_of_interest(candidate_species, query_dir):
    """Cross-reference Taxa of Interest (TOIs) against candidate species.

    Each TOI can be at any taxonomic level, so need to check at appropriate
    taxonomic level.
    """
    taxa_of_interest = config.get_toi_list_for_query(query_dir)
    if not taxa_of_interest:
        logger.info("No taxa of interest provided - writing flag 2 NA.")
        Flag.write(
            query_dir,
            FLAGS.TOI,
            FLAGS.NA,
        )
        logger.info("No taxa of interest provided - no output written.")
        return
    candidate_taxa_flattened = [
        {
            'rank': rank,
            'taxon': taxon,
            'species': hit['species'],
            'accession': hit['accession'],
            'identity': str(100 * hit['identity']) + '%',
        }
        for hit in candidate_species
        for rank, taxon in hit["taxonomy"].items()
    ]
    write_flag = True

    with (query_dir / config.TOI_DETECTED_CSV).open("w") as f:
        writer = csv.writer(f)
        writer.writerow(config.OUTPUTS.TOI_DETECTED_HEADER)

    for toi in taxa_of_interest:
        try:
            detected_taxon = [
                tax for tax in candidate_taxa_flattened
                if toi.lower() == tax['taxon'].lower()
            ][0]
        except IndexError:
            detected_taxon = {}
        _write_toi_detected(
            query_dir,
            toi,
            detected_taxon,
            write_flag=write_flag,
        )
        if detected_taxon:
            write_flag = False
    logger.info("Writing taxa of interest detection to"
                f" {query_dir / config.TOI_DETECTED_CSV}")


def _write_toi_detected(query_dir, toi, detected, write_flag=True):
    """Record whether a given TOI was detected and set flag."""
    if write_flag:
        if detected:
            value = FLAGS.A
        else:
            value = FLAGS.B
        Flag.write(
            query_dir,
            FLAGS.TOI,
            value,
        )
    with (query_dir / config.TOI_DETECTED_CSV).open("a") as f:
        writer = csv.writer(f)
        writer.writerow([
            toi,
            detected.get('rank', ''),
            detected.get('taxon', ''),
            detected.get('species', ''),
            detected.get('accession', ''),
            detected.get('identity', ''),
        ])


if __name__ == "__main__":
    main()
