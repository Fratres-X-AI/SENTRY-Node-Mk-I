"""Sanitize and publish committed test results under validation/published/."""

from __future__ import annotations

import json
import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_DIR = ROOT / "validation" / "reports" / "ci"
OUT = ROOT / "validation" / "published"

LOCAL_PATH_RE = re.compile(
    r"[A-Za-z]:\\Users\\[^\\\"]+|C:\\\\Users\\\\[^\\\"]+|/home/[^/\"]+|\\\\Users\\\\[^\\\"]+"
)


def _scrub(text: str) -> str:
    text = LOCAL_PATH_RE.sub("<local-path>", text)
    text = text.replace(str(ROOT).replace("\\", "\\\\"), "<repo-root>")
    text = text.replace(str(ROOT), "<repo-root>")
    text = text.replace(str(ROOT).replace("\\", "/"), "<repo-root>")
    return text


def _scrub_obj(obj: object) -> object:
    if isinstance(obj, dict):
        return {k: _scrub_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub_obj(v) for v in obj]
    if isinstance(obj, str):
        return _scrub(obj)
    return obj


def _write_results_md(summary: dict, audit: dict) -> str:
    gates = summary.get("gates", {})
    pytest = gates.get("pytest", {})
    cov = pytest.get("coverage", {})
    mypy = gates.get("mypy", {})
    scenarios = (gates.get("audit") or {}).get("scenarios") or []
    failure_modes = (audit.get("failure_modes") or {}).get("modes") or []

    lines = [
        "# SENTRY Node Mk I - Published Test Results",
        "",
        f"**Generated:** {summary.get('generated_at', '')}  ",
        f"**Source:** {summary.get('source', 'local')}  ",
        f"**Overall:** {'PASS' if summary.get('all_passed') else 'FAIL'}  ",
        f"**Version:** {(audit.get('version') or '0.5.0-darkspace-integrated')}",
        "",
        "This directory is committed on purpose so validation evidence is visible in the",
        "repository (not only as ephemeral GitHub Actions artifacts).",
        "",
        "## Gate summary",
        "",
        "| Gate | Result | Detail |",
        "|------|--------|--------|",
        f"| Pytest | {'PASS' if pytest.get('ok') else 'FAIL'} | {pytest.get('passed_count', pytest.get('passed', 0))}/{pytest.get('tests', 0)} in {pytest.get('time_s', 0)}s |",
        f"| Coverage (measured include set) | {'PASS' if cov.get('line_rate', 0) >= 100 else 'FAIL'} | {cov.get('line_rate', 0)}% / {cov.get('lines_covered', 0)}/{cov.get('lines_valid', 0)} lines |",
        f"| Mypy (strict) | {'PASS' if mypy.get('ok') or mypy.get('passed') else 'FAIL'} | {mypy.get('source_files', 0)} files / {mypy.get('errors', 0)} errors |",
        f"| Simulation smoke | {'PASS' if (gates.get('simulation') or {}).get('ok') else 'FAIL'} | intrusion path |",
        f"| Build readiness | {'PASS' if (gates.get('build_readiness') or {}).get('ok') else 'FAIL'} | software gate |",
        f"| Defense readiness audit | {'PASS' if (gates.get('audit') or {}).get('ok') else 'FAIL'} | overall {(gates.get('audit') or {}).get('overall')} |",
        "",
        "## Scenario battery",
        "",
        "| Scenario | Status | Frames | Max level | Mean CPU % | Mean W | Audit chain |",
        "|----------|--------|--------|-----------|------------|--------|-------------|",
    ]

    audit_scenarios = {s.get("scenario"): s for s in audit.get("scenarios") or [] if isinstance(s, dict)}
    for row in scenarios:
        name = row.get("name", "unknown")
        detail = audit_scenarios.get(name, {})
        power = detail.get("power") or {}
        lines.append(
            f"| {name} | {row.get('status')} | {detail.get('frames', '')} | "
            f"{detail.get('max_level', '')} | {power.get('mean_cpu_percent', '')} | "
            f"{power.get('mean_watts', '')} | "
            f"{'valid' if detail.get('audit_chain_valid') else detail.get('audit_chain_valid')} |"
        )

    lines.extend(
        [
            "",
            "## Failure modes",
            "",
            "| Mode | Passed | Max level | Detail |",
            "|------|--------|-----------|--------|",
        ]
    )
    for mode in failure_modes:
        if not isinstance(mode, dict):
            continue
        lines.append(
            f"| {mode.get('mode')} | {mode.get('passed')} | {mode.get('max_level', '')} | {mode.get('detail', '')} |"
        )

    lines.extend(
        [
            "",
            "## Machine-readable artifacts in this folder",
            "",
            "- `summary.json` - gate rollup",
            "- `pytest-junit.xml` - pytest JUnit",
            "- `coverage.xml` - coverage.xml",
            "- `defense-readiness-sentry.json` - full audit (paths sanitized)",
            "- `mypy.txt`, `simulation.txt`, `build_readiness.txt`, `audit.txt` - gate logs",
            "",
            "## Reproduce",
            "",
            "```bash",
            "python scripts/collect_ci_reports.py",
            "python scripts/publish_results.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    if not (CI_DIR / "summary.json").exists():
        raise SystemExit("missing validation/reports/ci/summary.json — run collect_ci_reports.py first")

    OUT.mkdir(parents=True, exist_ok=True)

    summary = json.loads((CI_DIR / "summary.json").read_text(encoding="utf-8"))
    summary["source"] = "committed-snapshot"
    summary["published_at"] = datetime.now(timezone.utc).isoformat()
    summary = _scrub_obj(summary)
    assert isinstance(summary, dict)

    audit_src = CI_DIR / "defense-readiness-sentry.json"
    if not audit_src.exists():
        audit_src = ROOT / "validation" / "reports" / "defense-readiness-sentry.json"
    audit: dict = {}
    if audit_src.exists():
        audit = _scrub_obj(json.loads(audit_src.read_text(encoding="utf-8")))  # type: ignore[assignment]

    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT / "defense-readiness-sentry.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "RESULTS.md").write_text(_write_results_md(summary, audit), encoding="utf-8")

    for name in (
        "pytest-junit.xml",
        "coverage.xml",
        "mypy.txt",
        "simulation.txt",
        "build_readiness.txt",
        "audit.txt",
    ):
        src = CI_DIR / name
        if not src.exists():
            continue
        text = _scrub(src.read_text(encoding="utf-8", errors="replace"))
        (OUT / name).write_text(text, encoding="utf-8")

    # Strip absolute paths from coverage XML filenames if present
    cov = OUT / "coverage.xml"
    if cov.exists():
        try:
            root = ET.parse(cov).getroot()
            for elem in root.iter():
                for attr in ("filename", "name"):
                    if attr in elem.attrib:
                        elem.attrib[attr] = elem.attrib[attr].replace("\\", "/")
                        # keep package-relative paths only
                        if "src/sentry" in elem.attrib[attr]:
                            elem.attrib[attr] = elem.attrib[attr].split("src/sentry", 1)[-1]
                            if not elem.attrib[attr].startswith("src/"):
                                elem.attrib[attr] = "src/sentry" + elem.attrib[attr]
            ET.ElementTree(root).write(cov, encoding="utf-8", xml_declaration=True)
        except ET.ParseError:
            pass

    # Do not commit bulky HTML coverage tree; XML + SUMMARY is enough.
    html_dir = OUT / "coverage_html"
    if html_dir.exists():
        shutil.rmtree(html_dir)

    print(f"published -> {OUT}")
    print(f"all_passed={summary.get('all_passed')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
