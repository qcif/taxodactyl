"""Render the pytest JSON report into a single-file HTML review page."""

from html import escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, pass_eval_context

_LIB_DIR = Path(__file__).parent
_STATIC_DIR = _LIB_DIR / "static"
_TEMPLATE_DIR = _LIB_DIR / "templates"

FAVICON = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
    "<path d='M9 2v12.5a3.5 3.5 0 007 0V2H9zm2 2h3v9h-3V4z' "
    "fill='%234f46e5'/>"
    "<circle cx='12' cy='16.5' r='1' fill='%234f46e5'/>"
    "</svg>"
)


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


def _promote_target(result: dict) -> str:
    fixture = result.get("fixture")
    if not fixture:
        return result.get("sample_id") or ""
    stem = Path(fixture).stem
    head = stem.split("_", 1)[0]
    return head if head.isdigit() else stem


def _promote_cmd(result: dict, reports_dir: str) -> str:
    target = _promote_target(result)
    if not target:
        return ""
    cmd = f"./testkit.py promote {target}"
    if reports_dir:
        cmd += f" -d {reports_dir}"
    return cmd


def _build_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=False,
    )

    @pass_eval_context
    def pretty_filter(eval_ctx, value):
        return _pretty(value)

    env.filters["pretty"] = pretty_filter
    return env


def render_html(data: dict) -> str:
    results = data.get("results", [])
    reports_dir = data.get("reports_dir", "") or ""

    enriched = []
    for r in results:
        enriched.append({
            **r,
            "fixture_label": _fixture_label(r),
            "drift_count": len(r.get("drifted") or []),
            "observed_link": _link("observed", r.get("observed_html")),
            "reference_link": _link("reference", r.get("reference_html")),
            "promote_cmd": _promote_cmd(r, reports_dir),
        })

    env = _build_env()
    template = env.get_template("review.html.j2")
    return template.render(
        favicon=FAVICON,
        css=(_STATIC_DIR / "review.css").read_text(),
        js=(_STATIC_DIR / "review.js").read_text(),
        generated_at=data.get("generated_at", "?"),
        reports_dir=reports_dir,
        total=len(results),
        passed=sum(1 for r in results if r["outcome"] == "passed"),
        failed=sum(1 for r in results if r["outcome"] == "failed"),
        errored=sum(1 for r in results if r["outcome"] == "error"),
        results=enriched,
    )
