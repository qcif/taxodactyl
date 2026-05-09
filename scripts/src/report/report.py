"""Entrypoint for rendering a workflow report."""

import base64
import csv
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import yaml
from Bio import SeqIO
from jinja2 import Environment, FileSystemLoader

from src.utils import config, deduplicate, serialize
from src.utils.errors import ErrorLog, LOCATIONS
from src.utils.flags import FLAGS, Flag, level_to_bs_class

from .filters.css_hash import css_hash
from .outcomes import DetectedTaxon

logger = logging.getLogger(__name__)
config = config.Config()

TEMPLATE_DIR = Path(__file__).parent / 'templates'
STATIC_DIR = Path(__file__).parent / 'static'


def render(
    query,
    bold=False,
    params_json=None,
    versions_yml=None,
):
    """Render to HTML report to the configured output directory."""
    query_ix = config.get_query_ix(query)
    j2 = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    j2.filters['css_hash'] = css_hash
    j2.filters['bs_class'] = level_to_bs_class
    template = j2.get_template('index.html')
    context = _get_report_context(query_ix, bold, params_json, versions_yml)

    path = config.output_dir / 'report_context.json'
    with path.open('w') as f:
        print(f"Writing report context to {path}")
        json.dump(context, f, default=serialize, indent=2)

    static_files = _get_static_file_contents()
    rendered_html = template.render(**context, **static_files)

    if bold:
        rendered_html = re.sub(r"\bidentity\b", "similarity", rendered_html)
        rendered_html = re.sub(r"\bIdentity\b", "Similarity", rendered_html)

    report_path = config.get_report_path(query_ix, bold=bold)
    with open(report_path, 'w', encoding="utf-8") as f:
        f.write(rendered_html)
    logger.info(f"HTML document written to {report_path}")


def _get_static_file_contents():
    """Return the static files content as strings."""
    static_files = {}
    for root, _, files in os.walk(STATIC_DIR):
        root = Path(root)
        if root.name == 'css':
            static_files['css'] = [
                f'/* {f} */\n' + (root / f).read_text()
                for f in sorted(files)
            ]
        elif root.name == 'js':
            static_files['js'] = sorted([
                f'/* {f} */\n' + (root / f).read_text(encoding="utf-8")
                for f in sorted(files)
            ])
        elif root.name == 'img':
            static_files['img'] = {
                f: _get_img_src(root / f)
                for f in sorted(files)
            }
    return {'static': static_files}


def _get_img_src(path):
    """Return the base64 encoded image source as an HTML img src property."""
    if not path.exists():
        logger.warning(f"Expected image {path} does not exist. Replacing with"
                       " placeholder image.")
        path = config.placeholder_img_path
    ext = path.suffix[1:]
    return (
        f"data:image/{ext};base64,"
        + base64.b64encode(path.read_bytes()).decode()
    )


def _get_report_context(query_ix, bold, params_json, versions_yml):
    """Build the context for the report template."""
    query_fasta_str = config.read_query_fasta(query_ix).format('fasta')
    hits = config.read_hits_json(query_ix)['hits']
    id_key = "hit_id" if bold else "accession"
    html_title = (
        'BOLD - ' + config.report.title
        if bold
        else config.report.title
    )
    hits_taxonomy = (
        _load_taxonomies_bold(hits)
        if bold
        else _load_taxonomies(hits)
    )
    tree_accessions = {
        acc: (
            'Unknown'
            if hits_taxonomy.get(acc) is None
            else hits_taxonomy.get(acc, {}).get('species')
        )
        for acc in _get_phylogeny_accessions(query_ix, hits, id_key)
    }
    return {
        'title': config.report.title,
        'html_title': html_title,
        'workflow_params': _read_params_json(params_json),
        'workflow_versions': _read_versions_yml(versions_yml),
        'facility': config.inputs.facility_name,
        'analyst_name': config.inputs.analyst_name,
        'start_time': config.timestamp,
        'end_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'wall_time': _get_walltime(),
        'metadata': _get_metadata(query_ix),
        'locus_provided': config.locus_was_provided_for(query_ix),
        'config': config,
        'flag_definitions': config.read_flag_details_csv(),
        'input_fasta': query_fasta_str,
        'conclusions': _draw_conclusions(query_ix, hits),
        'hits': hits,
        'candidates': _get_candidates(query_ix),
        'hits_taxonomy': hits_taxonomy,
        'taxonomic_ranks': [
            'domain',
            'kingdom',
            'phylum',
            'class',
            'order',
            'family',
            'genus',
            'species',
        ],
        'candidates_boxplot_src': _get_boxplot_src(query_ix),
        'toi_rows': _read_toi_rows(query_ix),
        'tois_detected': _read_toi_detected(query_ix),
        'aggregated_sources': _read_source_diversity(query_ix),
        'db_coverage': _read_db_coverage(query_ix),
        'tree_nwk_str': (config.get_query_dir(query_ix)
                         / config.tree_nwk_filename).read_text().strip(),
        'tree_accessions': tree_accessions,
        'tree_species': deduplicate(tree_accessions.values()),
        'error_log': ErrorLog(config.get_query_dir(query_ix)),
        'bold': bold,
        # rendering functions:
        'url_from_accession': config.url_from_accession,
        'error_locations': LOCATIONS,
    }


def _read_params_json(params_json: Path) -> dict[str, str]:
    """Read the workflow parameters from a JSON file."""
    if not params_json:
        return {}
    if not params_json.exists():
        logger.warning(f"Parameters JSON file {params_json} does not exist.")
        return {}
    return json.loads(params_json.read_text())


def _read_versions_yml(versions_yml: Path) -> dict[str, str]:
    """Read the workflow versions from a YAML file."""
    if not versions_yml:
        return {}
    if not versions_yml.exists():
        logger.warning(f"Versions YAML file {versions_yml} does not exist.")
        return {}
    with versions_yml.open() as f:
        data = yaml.safe_load(f)
    return {
        k: v
        for versions in data.values()
        for k, v in versions.items()
    }


def _get_walltime():
    """Return wall time since start of the workflow.
    Returns a dict of hours, minutes, seconds.
    """
    if not config.start_time:
        return {}
    seconds = (datetime.now() - config.start_time).total_seconds()
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return {
        'hours': int(hours),
        'minutes': int(minutes),
        'seconds': int(seconds),
    }


def _get_metadata(query_ix):
    """Return mock metadata for the report."""
    sample_id = config.get_sample_id(query_ix)
    return {
        'sample_id': sample_id,
        **config.metadata[sample_id],
    }


def _draw_conclusions(query_ix, hits):
    """Determine conclusions from outputs flags and files."""
    flags = Flag.read(query_ix)
    return {
        'flags': flags,
        'summary': {
            'result': _get_taxonomic_result(query_ix, flags),
            'pmi': _get_pmi_result(flags),
            'toi': _get_toi_result(query_ix, flags),
        },
        'hits': {
            'lowest_identity': min(
                hit['identity'] for hit in hits
            ) if hits else None,
        },
    }


def _get_taxonomic_result(query_ix, flags):
    """Determine the taxonomic result from the flags."""
    path = config.get_query_dir(query_ix) / config.taxonomy_id_csv
    flag_1 = flags[FLAGS.POSITIVE_ID]
    if flag_1.value == FLAGS.A:
        # Should only be 'success' if also flag 4A
        sources_verified = all([
            flag.level == 1
            for flag in flags[FLAGS.SOURCES].values()
        ])
        with path.open() as f:
            reader = csv.DictReader(f)
            hit = next(reader)
        return {
            'confirmed': True,
            'species': hit['species'],
            'bs_class': 'success' if sources_verified else 'warning',
            'level': 1 if sources_verified else 2,
            'sources_verified': sources_verified,
        }
    return {
        'confirmed': False,
        'species': None,
        'bs_class': flag_1.bs_class,
        'level': flag_1.level,
    }


def _get_pmi_result(flags):
    """Determine the preliminary ID confirmation from the flags."""
    flag_1 = flags[FLAGS.POSITIVE_ID]
    if flag_1.value != FLAGS.A:
        return {
            'confirmed': False,
            'explanation': "Inconclusive taxonomic identity (Flag"
                           f" {FLAGS.POSITIVE_ID}{flag_1.value})",
            'bs-class': 'secondary',
            'tooltip': (
                "The preliminary ID cannot be confirmed or rejected, because"
                " we did not identify a conclusive taxonomy for the sample."
                ),
        }
    flag_7 = flags[FLAGS.PMI]
    if flag_7.value == FLAGS.A:
        return {
            'confirmed': True,
            'explanation': f'<strong>Flag 7{flag_7.value}</strong>:'
                           f' {flag_7.explanation}',
            'bs-class': 'success',
        }
    return {
        'confirmed': False,
        'explanation': f'<strong>Flag 7{flag_7.value}</strong>:'
                       f' {flag_7.explanation}',
        'bs-class': 'danger',
    }


def _get_toi_result(query_ix, flags):
    """Determine the taxa of interest detection from the flags."""
    query_dir = config.get_query_dir(query_ix)
    path = query_dir / config.toi_detected_csv
    if not path.exists():
        logger.info(f"No taxa of interest file available at {path}")
        return
    with path.open() as f:
        reader = csv.DictReader(f)
        detected_tois = [
            DetectedTaxon(*[
                row.get(colname)
                for colname in config.toi_detected_header
            ])
            for row in reader
            if row.get(config.toi_detected_header[1])
        ]
    flag_2 = flags[FLAGS.TOI]
    ruled_out = flag_2.value == FLAGS.B

    return {
        'detected': detected_tois,
        'flag': flag_2,
        'ruled_out': ruled_out,
        'bs-class': 'success' if detected_tois else 'danger',
    }


def _get_candidates(query_ix):
    """Read data for the candidate hits/taxa."""
    flags = Flag.read(query_ix)
    query_dir = config.get_query_dir(query_ix)
    with open(query_dir / config.candidates_json) as f:
        candidates = json.load(f)
    candidates['fasta'] = {
        seq.id: seq.format("fasta")
        for seq in config.read_fasta(query_dir / config.candidates_fasta)
    }
    candidates['strict'] = (
        flags[FLAGS.POSITIVE_ID].value
        not in (FLAGS.D, FLAGS.E))
    return candidates


def _load_taxonomies(hits):
    run_taxonomies = config.read_taxonomy_file()
    return {
        hit['accession']: run_taxonomies.get(hit['accession'])
        for hit in hits
    }


def _load_taxonomies_bold(hits):
    return {
        hit['accession']: {
            key: hit.get("taxonomy", {}).get(key, "")
            for key in (
                "phylum",
                "class",
                "order",
                "family",
                "genus",
                "species",
            )
        }
        for hit in hits if 'accession' in hit
    }


def _get_boxplot_src(query_ix) -> Path:
    """Return the path to the boxplot image if it exists."""
    path = config.get_query_dir(query_ix) / config.boxplot_img_filename
    if path.exists():
        return _get_img_src(path)
    return None


def _read_toi_rows(query_ix):
    """Read the taxa of interest detected from the CSV file."""
    path = config.get_query_dir(query_ix) / config.toi_detected_csv
    if not path.exists():
        return []
    with path.open() as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def _read_toi_detected(query_ix):
    """Read the taxa of interest detected from the CSV file."""
    path = config.get_query_dir(query_ix) / config.toi_detected_csv
    if not path.exists():
        return {}
    with path.open() as f:
        reader = csv.DictReader(f)
        return {
            row['Taxon of interest']: bool(row['Match rank'])
            for row in reader
        }


def _read_source_diversity(query_ix):
    """Read the source diversity table from the CSV file."""
    path = config.get_query_dir(query_ix) / config.independent_sources_json
    if not path.exists():
        logger.warning(f'No source diversity file found at {path}')
        return {}
    with path.open() as f:
        return json.load(f)


def _read_db_coverage(query_ix):
    """Read the database coverage table from the CSV file."""
    path = config.get_query_dir(query_ix) / config.db_coverage_json
    if not path.exists():
        logger.warning(f'No database coverage file found at {path}')
        return {}
    with path.open() as f:
        data = json.load(f)
    coverage_data = data['coverage']
    ncbi_blast_urls = data['ncbi_blast_urls']
    for target_type, targets in coverage_data.items():
        for target in targets:
            path = (
                config.get_query_dir(query_ix)
                / config.get_map_filename_for_target(target)
            )
            coverage_data[target_type][target]['map_exists'] = path.exists()
            coverage_data[target_type][target][
                'map_src_base64'] = _get_img_src(path)
    return {
        'full': coverage_data,
        'summary': _get_db_cov_summary(coverage_data),
        'ncbi_blast_urls': ncbi_blast_urls,
    }


def _get_db_cov_summary(db_coverage_data):
    """Get a summary of the database coverage."""
    def _coverage_percent(data: dict) -> float:
        """Calculate the coverage percentage."""
        if not (data and isinstance(data, dict)):
            return None
        total = len(data)
        covered = len([
            x for x in data.values() if x
        ])
        return round(covered / total, 2) if total else 0.0

    summary = {}
    for target_type, targets in db_coverage_data.items():
        for target, data in targets.items():
            summary.setdefault(target_type, {})[target] = {
                'target': data['target'],
                'related': _coverage_percent(data['related']),
                'country': _coverage_percent(data['country']),
            }
    return summary


def _get_phylogeny_accessions(query_ix, hits, id_key):
    """Read the phylogeny accessions from the FASTA file.

    Sort them so they match their appearance in hits list.
    """
    path = config.get_query_dir(query_ix) / config.phylogeny_fasta
    if not path.exists():
        logger.warning(f'No phylogeny accessions file found at {path}')
        return []
    with path.open() as f:
        accessions = [
            seq.id
            for seq in SeqIO.parse(f, "fasta")
        ]
    sorted_hits = []
    for hit in hits:
        acc = hit.get(id_key)
        if acc in accessions and acc not in sorted_hits:
            sorted_hits.append(acc)
    return sorted_hits


if __name__ == '__main__':
    query_ix = 0
    render(query_ix)
