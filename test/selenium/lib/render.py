"""Render the pytest JSON report into a single-file HTML review page."""

from html import escape
from pathlib import Path


# Minimal test-tube SVG, base64-embedded so the HTML remains self-contained.
FAVICON = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
    "<path d='M9 2v12.5a3.5 3.5 0 007 0V2H9zm2 2h3v9h-3V4z' "
    "fill='%234f46e5'/>"
    "<circle cx='12' cy='16.5' r='1' fill='%234f46e5'/>"
    "</svg>"
)


CSS = """
* { box-sizing: border-box; }
body {
    font-family: -apple-system, system-ui, sans-serif;
    margin: 0;
    color: #1f2937;
    background: #f9fafb;
}
header {
    background: #111827;
    color: #f9fafb;
    padding: 1.25rem 2rem;
}
header h1 { margin: 0 0 0.25rem 0; font-size: 1.25rem; }
header .meta { font-size: 0.85rem; opacity: 0.7; }
main { padding: 1.5rem 2rem; max-width: 1200px; margin: 0 auto; }
.summary {
    display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap;
}
.summary .box {
    background: white;
    border-radius: 6px;
    padding: 0.75rem 1rem;
    min-width: 8rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.summary .box .label {
    font-size: 0.75rem; text-transform: uppercase; color: #6b7280;
}
.summary .box .value { font-size: 1.5rem; font-weight: 600; }
.summary .box.passed .value { color: #16a34a; }
.summary .box.failed .value { color: #dc2626; }
.summary .box.error  .value { color: #ea580c; }
table.results {
    width: 100%;
    border-collapse: collapse;
    background: white;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    border-radius: 6px;
    overflow: hidden;
}
table.results th, table.results td {
    text-align: left;
    padding: 0.6rem 0.9rem;
    border-bottom: 1px solid #e5e7eb;
    font-size: 0.9rem;
}
table.results th { background: #f3f4f6; font-weight: 600; }
tr.row-failed td:first-child { border-left: 3px solid #dc2626; }
tr.row-error  td:first-child { border-left: 3px solid #ea580c; }
tr.row-passed td:first-child { border-left: 3px solid #16a34a; }
.badge {
    display: inline-block; padding: 0.15rem 0.55rem;
    border-radius: 999px; font-size: 0.75rem; font-weight: 600;
    text-transform: uppercase;
}
.badge.passed { background: #dcfce7; color: #166534; }
.badge.failed { background: #fee2e2; color: #991b1b; }
.badge.error  { background: #ffedd5; color: #9a3412; }
a.link {
    color: #2563eb; text-decoration: none; margin-right: 0.75rem;
    font-size: 0.85rem;
}
a.link:hover { text-decoration: underline; }
details {
    background: white; margin: 0.75rem 0; padding: 0 1rem;
    border-radius: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
details summary {
    cursor: pointer; padding: 0.75rem 0; font-weight: 600;
}
details .links { margin: 0.25rem 0 0.75rem 0; }
table.drift {
    width: 100%; border-collapse: collapse; margin: 0.5rem 0 1rem 0;
    font-size: 0.85rem;
}
table.drift th, table.drift td {
    text-align: left; padding: 0.4rem 0.6rem;
    border-bottom: 1px solid #f3f4f6;
    vertical-align: top;
}
table.drift th { background: #f9fafb; font-weight: 600; }
table.drift code {
    background: #f3f4f6; padding: 0.05rem 0.35rem;
    border-radius: 3px; font-size: 0.85rem;
    word-break: break-word;
}
.error-message {
    background: #fef2f2; border: 1px solid #fecaca;
    color: #991b1b; padding: 0.75rem 1rem;
    border-radius: 6px; margin: 0.5rem 0 1rem 0;
    font-family: ui-monospace, monospace; font-size: 0.85rem;
    white-space: pre-wrap;
}
"""


def _link(label: str, path) -> str:
    if not path:
        return (
            "<span class='link' style='color:#9ca3af'>"
            f"{escape(label)}</span>"
        )
    raw = str(path)
    uri = raw if raw.startswith("file://") else Path(path).as_uri()
    return (
        f"<a class='link' href='{escape(uri)}' target='_blank'>"
        f"{escape(label)}</a>"
    )


def _pretty(value) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(_pretty(v) for v in value) + "]"
    if isinstance(value, str):
        return repr(value)
    return str(value)


def _fixture_label(result: dict) -> str:
    fixture = result.get("fixture")
    return Path(fixture).name if fixture else "?"


def _row(result: dict) -> str:
    outcome = result["outcome"]
    drift_count = len(result.get("drifted") or [])
    return (
        f"<tr class='row-{outcome}'>"
        f"<td><strong>{escape(result['sample_id'] or '?')}</strong></td>"
        f"<td>{escape(_fixture_label(result))}</td>"
        f"<td><span class='badge {outcome}'>{outcome}</span></td>"
        f"<td>{drift_count}</td>"
        f"<td>{result['duration_s']}s</td>"
        f"<td>"
        f"{_link('observed', result.get('observed_html'))}"
        f"{_link('reference', result.get('reference_html'))}"
        f"</td>"
        f"</tr>"
    )


def _drift_details(result: dict) -> str:
    if result["outcome"] == "passed":
        return ""

    parts = [
        f"<details open>"
        f"<summary>"
        f"{escape(result['sample_id'] or '?')}"
        f" — {escape(_fixture_label(result))}"
        f" ({result['outcome']})"
        f"</summary>"
        f"<div class='links'>"
        f"{_link('Open observed report', result.get('observed_html'))}"
        f"{_link('Open reference report', result.get('reference_html'))}"
        f"</div>"
    ]

    if result.get("error_message"):
        parts.append(
            f"<div class='error-message'>"
            f"{escape(result['error_message'])}"
            f"</div>"
        )

    drifted = result.get("drifted") or []
    if drifted:
        parts.append(
            "<table class='drift'>"
            "<tr><th>Field</th><th>Type</th>"
            "<th>Expected</th><th>Observed</th></tr>"
        )
        for d in drifted:
            parts.append(
                f"<tr>"
                f"<td><code>{escape(d['component'])}."
                f"{escape(d['assertion_id'])}</code></td>"
                f"<td>{escape(d['type'])}</td>"
                f"<td><code>{escape(_pretty(d['expected']))}</code></td>"
                f"<td><code>{escape(_pretty(d['observed']))}</code></td>"
                f"</tr>"
            )
        parts.append("</table>")

    parts.append("</details>")
    return "".join(parts)


def render_html(data: dict) -> str:
    results = data.get("results", [])
    total = len(results)
    passed = sum(1 for r in results if r["outcome"] == "passed")
    failed = sum(1 for r in results if r["outcome"] == "failed")
    errored = sum(1 for r in results if r["outcome"] == "error")

    rows = "".join(_row(r) for r in results)
    details = "".join(
        _drift_details(r) for r in results if r["outcome"] != "passed"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Selenium test review</title>
<link rel="icon" href="{FAVICON}">
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>Selenium test review</h1>
  <div class="meta">
    Generated {escape(data.get('generated_at', '?'))}
    &middot; reports-dir: <code>{escape(data.get('reports_dir', '?'))}</code>
  </div>
</header>
<main>
  <section class="summary">
    <div class="box"><div class="label">Total</div>
      <div class="value">{total}</div></div>
    <div class="box passed"><div class="label">Passed</div>
      <div class="value">{passed}</div></div>
    <div class="box failed"><div class="label">Failed</div>
      <div class="value">{failed}</div></div>
    <div class="box error"><div class="label">Errored</div>
      <div class="value">{errored}</div></div>
  </section>

  <table class="results">
    <thead><tr>
      <th>Sample</th><th>Fixture</th><th>Outcome</th>
      <th>Drift</th><th>Duration</th><th>Report</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>

  {details}
</main>
</body>
</html>
"""
