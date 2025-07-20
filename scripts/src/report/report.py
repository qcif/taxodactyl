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
from jinja2 import Environment, FileSystemLoader

from src.utils import config, serialize
from src.utils.errors import ErrorLog, LOCATIONS
from src.utils.flags import FLAGS, Flag, TARGETS, level_to_bs_class

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
                for f in files
            ]
        elif root.name == 'js':
            static_files['js'] = sorted([
                f'/* {f} */\n' + (root / f).read_text(encoding="utf-8")
                for f in files
            ])
        elif root.name == 'img':
            static_files['img'] = {
                f: _get_img_src(root / f)
                for f in files
            }
    return {'static': static_files}


def _get_img_src(path):
    """Return the base64 encoded image source as an HTML img src property."""
    if not path.exists():
        logger.warning(f"Expected image {path} does not exist. Replacing with"
                       " placeholder image.")
        path = config.PLACEHOLDER_IMG_PATH
    ext = path.suffix[1:]
    return (
        f"data:image/{ext};base64,"
        + base64.b64encode(path.read_bytes()).decode()
    )


def _get_report_context(query_ix, bold, params_json, versions_yml):
    """Build the context for the report template."""
    query_fasta_str = config.read_query_fasta(query_ix).format('fasta')
    hits = config.read_hits_json(query_ix)['hits']
    html_title = (
        'BOLD - ' + config.REPORT.TITLE
        if bold
        else config.REPORT.TITLE
    )
    return {
        'title': config.REPORT.TITLE,
        'html_title': html_title,
        'workflow_params': _read_params_json(params_json),
        'workflow_versions': _read_versions_yml(versions_yml),
        'facility': config.INPUTS.FACILITY_NAME,
        'analyst_name': config.INPUTS.ANALYST_NAME,
        'start_time': config.start_time.strftime("%Y-%m-%d %H:%M:%S"),
        'end_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'wall_time': _get_walltime(),
        'metadata': _get_metadata(query_ix),
        'locus_provided': config.locus_was_provided_for(query_ix),
        'config': config,
        'flag_definitions': config.read_flag_details_csv(),
        'input_fasta': query_fasta_str,
        'conclusions': _draw_conclusions(query_ix),
        'hits': hits,
        'candidates': _get_candidates(query_ix),
        'hits_taxonomy': (
            _load_taxonomies_bold(hits) if bold else _load_taxonomies(hits)
        ),
        'candidates_boxplot_src': _get_boxplot_src(query_ix),
        'toi_rows': _read_toi_rows(query_ix),
        'tois_detected': _read_toi_detected(query_ix),
        'aggregated_sources': _read_source_diversity(query_ix),
        'db_coverage': _read_db_coverage(query_ix),
        'tree_nwk_str': (config.get_query_dir(query_ix)
                         / config.TREE_NWK_FILENAME).read_text().strip(),
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


def _draw_conclusions(query_ix):
    """Determine conclusions from outputs flags and files."""
    flags = Flag.read(query_ix)
    return {
        'flags': flags,
        'summary': {
            'result': _get_taxonomic_result(query_ix, flags),
            'pmi': _get_pmi_result(flags),
            'toi': _get_toi_result(query_ix, flags),
        }
    }


def _get_taxonomic_result(query_ix, flags):
    """Determine the taxonomic result from the flags."""
    path = config.get_query_dir(query_ix) / config.TAXONOMY_ID_CSV
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
    path = query_dir / config.TOI_DETECTED_CSV
    if not path.exists():
        logger.info(f"No taxa of interest file available at {path}")
        return
    with path.open() as f:
        reader = csv.DictReader(f)
        detected_tois = [
            DetectedTaxon(*[
                row.get(colname)
                for colname in config.OUTPUTS.TOI_DETECTED_HEADER
            ])
            for row in reader
            if row.get(config.OUTPUTS.TOI_DETECTED_HEADER[1])
        ]
    flag_2 = flags[FLAGS.TOI]
    ruled_out = flag_2.value == FLAGS.B
    criteria = [flag_2]

    if TARGETS.TOI in flags[FLAGS.DB_COVERAGE_TARGET]:
        flags_5_1_targets = flags[FLAGS.DB_COVERAGE_TARGET][TARGETS.TOI]
        flag_5_1_max = max(
            flags_5_1_targets.values(),
            # Rank NA values the lowest so they don't clobber proper results
            key=lambda x: x.value if x.value != 'NA' else '0',
        )
        flags_5_2_targets = flags[FLAGS.DB_COVERAGE_RELATED][TARGETS.TOI]
        flag_5_2_max = max(
            flags_5_2_targets.values(),
            # Rank NA values the lowest so they don't clobber proper results
            key=lambda x: x.value if x.value != 'NA' else '0',
        )
        ruled_out = (
            ruled_out
            and flag_5_1_max.value == FLAGS.A
            and flag_5_2_max.value == FLAGS.A
        )
        criteria += [flag_5_1_max, flag_5_2_max]

    return {
        'detected': detected_tois,
        'flags': criteria,
        'ruled_out': ruled_out,
        'bs-class': 'success' if detected_tois else 'danger',
    }


def _get_candidates(query_ix):
    """Read data for the candidate hits/taxa."""
    flags = Flag.read(query_ix)
    query_dir = config.get_query_dir(query_ix)
    with open(query_dir / config.CANDIDATES_JSON) as f:
        candidates = json.load(f)
    candidates['fasta'] = {
        seq.id: seq.format("fasta")
        for seq in config.read_fasta(query_dir / config.CANDIDATES_FASTA)
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
    path = config.get_query_dir(query_ix) / config.BOXPLOT_IMG_FILENAME
    if path.exists():
        return _get_img_src(path)
    return None


def _read_toi_rows(query_ix):
    """Read the taxa of interest detected from the CSV file."""
    path = config.get_query_dir(query_ix) / config.TOI_DETECTED_CSV
    if not path.exists():
        return []
    with path.open() as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def _read_toi_detected(query_ix):
    """Read the taxa of interest detected from the CSV file."""
    path = config.get_query_dir(query_ix) / config.TOI_DETECTED_CSV
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
    path = config.get_query_dir(query_ix) / config.INDEPENDENT_SOURCES_JSON
    if not path.exists():
        logger.warning(f'No source diversity file found at {path}')
        return {}
    with path.open() as f:
        return json.load(f)


def _read_db_coverage(query_ix):
    """Read the database coverage table from the CSV file."""
    path = config.get_query_dir(query_ix) / config.DB_COVERAGE_JSON
    if not path.exists():
        logger.warning(f'No database coverage file found at {path}')
        return {}
    with path.open() as f:
        data = json.load(f)
    for target_type, targets in data.items():
        for target in targets:
            path = (
                config.get_query_dir(query_ix)
                / config.get_map_filename_for_target(target)
            )
            data[target_type][target]['map_exists'] = path.exists()
            data[target_type][target]['map_src_base64'] = _get_img_src(path)
    return data


if __name__ == '__main__':
    query_ix = 0
    render(query_ix)
