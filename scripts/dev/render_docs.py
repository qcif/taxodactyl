"""Render documentation in Markdown format to HTML."""

import json
import sys
from pathlib import Path

import markdown2
from jinja2 import Environment, FileSystemLoader, Template

sys.path.append(str(Path(__file__).resolve().parents[1]))
from src.utils.config import Config  # noqa: E402

config = Config()

ROOT_DIR = Path(__file__).resolve().parents[2]
DOCS_SRC_DIR = ROOT_DIR / 'docs/src'
DOCS_DEST_DIR = ROOT_DIR / 'docs'
ALLOWED_LOCI_PATH = ROOT_DIR / 'scripts/config/loci.json'
ALLOWED_LOCI_TEMPLATE = 'allowed-loci.html'


def main():
    DOCS_DEST_DIR.mkdir(parents=True, exist_ok=True)
    for md_file in DOCS_SRC_DIR.glob('*.md'):
        dest_filename = md_file.stem + '.html'
        dest_path = DOCS_DEST_DIR / dest_filename
        md_content = md_file.read_text(encoding='utf-8')
        html_body = markdown2.markdown(md_content, extras={
            # Docs: https://github.com/trentm/python-markdown2/wiki/Extras
            "tables": True,
            "code-friendly": True,
            "html-classes": {
                'table': 'table table-striped',
            },
            "header-ids": True,
            "fenced-code-blocks": True,
        })
        html_body_rendered = Template(html_body).render(
            config=config,
        )
        title = md_file.stem.replace('-', ' ').replace('_', ' ').capitalize()
        html_doc = render_html('header.html', {
            'body': html_body_rendered,
            'title': title,
        })
        dest_path.write_text(html_doc, encoding='utf-8')
        print(f"Rendered {md_file} -> {dest_path}")

    render_allowed_loci()


def render_html(template, context):
    j2 = Environment(
        loader=FileSystemLoader(DOCS_SRC_DIR),
        autoescape=True,
    )
    return j2.get_template(template).render(**context)


def render_allowed_loci():
    data = json.loads(ALLOWED_LOCI_PATH.read_text(encoding='utf-8'))
    loci_list = [
        item
        for group in data.values()
        for loci in group.values()
        for item in loci
    ]
    html_doc = render_html(ALLOWED_LOCI_TEMPLATE, {
        'title': 'List of permitted loci',
        'loci': loci_list,
    })
    dest_path = DOCS_DEST_DIR / ALLOWED_LOCI_TEMPLATE
    dest_path.write_text(html_doc, encoding='utf-8')
    print(f"Rendered allowed loci documentation to {dest_path}")


if __name__ == '__main__':
    main()
