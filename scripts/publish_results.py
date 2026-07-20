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


def _gate_pass(flag: object) -> str:
    return "PASS" if flag else "FAIL"


def _write_results_md(summary: dict, audit: dict) -> str:
    gates = summary.get("gates", {})
    pytest = gates.get("pytest", {})
    cov = pytest.get("coverage", {})
    mypy = gates.get("mypy", {})
    scenarios = (gates.get("audit") or {}).get("scenarios") or []
    failure_modes = (audit.get("failure_modes") or {}).get("modes") or []
    version = audit.get("version") or "0.5.0-darkspace-integrated"
    overall = "PASS" if summary.get("all_passed") else "FAIL"
    generated = summary.get("generated_at", "")

    failure_meaning = {
        "sensor_dropout_rf": "RF loss degrades confidence; does not fabricate RED",
        "thermal_throttle_jamming": "Thermal + jamming enters safe HOLD",
        "tamper_during_intrusion": "Tamper dominates; HOLD wins",
        "low_power_duty_cycle": "Power discipline retained",
        "deployment_chain_break": "Broken chain reported as non-operational",
        "deployment_entanglement": "Entangled nodes do not fake mesh readiness",
        "deployment_antenna_damage": "Damaged antennas fail BIT honestly",
        "deployment_alert_suppression": "Alerts suppressed until operational phase",
    }

    lines = [
        "# SENTRY Node Mk I - Validation Evidence",
        "",
        "**Maturity:** software-gate prototype (pre-physical)  ",
        f"**Version:** `{version}`  ",
        f"**Snapshot:** {generated}  ",
        f"**Overall software gates:** {overall}  ",
        "",
        "Fratres X AI standard: physics first, reviewable gates, conservative claims.",
        "This folder is committed evidence - not marketing copy.",
        "",
        "## What this proves",
        "",
        "| Claim | Status | Evidence |",
        "|-------|--------|----------|",
        "| Threat scoring responds correctly across benign / intrusion / jamming / low-vis | Proven in simulation | Scenario battery below |",
        "| HMAC audit chain detects tampering and remains valid on clean runs | Proven in CI/sim | Audit + tamper probe |",
        "| Strict typing holds on the Python package | Proven | Mypy gate |",
        "| Unit tests for the measured core pass | Proven | Pytest gate |",
        "| Mean simulated power stays under the 5 W target | Proven in sim | Scenario power columns |",
        "| Field FP/FN, RF front-end performance, Pi GPIO/USB stack | **Not proven** | Requires G1-G5 hardware gates |",
        "| Chain-deploy / high-g launch survival for COTS Pi nodes | **Not a product claim** | Stress sims show near-zero survival - by design |",
        "",
        "## How to read this report",
        "",
        "- **Scenario PASS** means the guardian reached the expected alert class and kept a valid audit chain.",
        "- **Failure-mode PASS** means the software correctly handled injected degradation. Counts like `0/8 operational` are expected outcomes under destructive stress - not a silent product failure.",
        f"- **Coverage 100%** applies only to the **measured include set** (currently {cov.get('lines_valid', 0)} statements). Hardware, GPU, and deployment modules omitted from the fail-under gate are not claimed covered.",
        "",
        "## Gate summary",
        "",
        "| Gate | Result | Detail |",
        "|------|--------|--------|",
        f"| Pytest | {_gate_pass(pytest.get('ok'))} | {pytest.get('passed_count', pytest.get('passed', 0))}/{pytest.get('tests', 0)} in {pytest.get('time_s', 0)} s |",
        f"| Coverage (include set) | {_gate_pass(cov.get('line_rate', 0) >= 100)} | {cov.get('line_rate', 0)}% of {cov.get('lines_valid', 0)} measured lines |",
        f"| Mypy (strict) | {_gate_pass(mypy.get('ok') or mypy.get('passed'))} | {mypy.get('source_files', 0)} files, {mypy.get('errors', 0)} errors |",
        f"| Simulation smoke | {_gate_pass((gates.get('simulation') or {}).get('ok'))} | intrusion path, audit valid |",
        f"| Build readiness (software) | {_gate_pass((gates.get('build_readiness') or {}).get('ok'))} | required files + site layout |",
        f"| Defense readiness audit | {_gate_pass((gates.get('audit') or {}).get('ok'))} | overall {(gates.get('audit') or {}).get('overall')} |",
        "",
        "## Scenario battery (expected behavior)",
        "",
        "| Scenario | Result | Max level | Mean CPU % | Mean W | Audit |",
        "|----------|--------|-----------|------------|--------|-------|",
    ]

    audit_scenarios = {
        s.get("scenario"): s for s in (audit.get("scenarios") or []) if isinstance(s, dict)
    }
    for row in scenarios:
        name = row.get("name", "unknown")
        detail = audit_scenarios.get(name, {})
        power = detail.get("power") or {}
        audit_ok = detail.get("audit_chain_valid")
        audit_label = "valid" if audit_ok else ("invalid" if audit_ok is False else "")
        lines.append(
            f"| {name} | {row.get('status')} | {detail.get('max_level', '')} | "
            f"{power.get('mean_cpu_percent', '')} | {power.get('mean_watts', '')} | {audit_label} |"
        )

    lines.extend(
        [
            "",
            "Interpretation: quiet scene stays CLEAR; intrusion escalates; jamming forces HOLD;",
            "degraded visibility stays elevated but not catastrophic.",
            "",
            "## Resilience battery (injected faults)",
            "",
            "These cases pass when the node **refuses to lie** under bad conditions.",
            "",
            "| Mode | Gate | Observed | Meaning |",
            "|------|------|----------|---------|",
        ]
    )
    for mode in failure_modes:
        if not isinstance(mode, dict):
            continue
        key = str(mode.get("mode", ""))
        passed = bool(mode.get("passed"))
        observed = mode.get("detail") or mode.get("max_level") or ""
        meaning = failure_meaning.get(key, "Injected fault handled without false readiness")
        lines.append(
            f"| {key} | {_gate_pass(passed)} | {observed} | {meaning} |"
        )

    lines.extend(
        [
            "",
            "## Explicit non-claims",
            "",
            "- Not field-validated. No outdoor FP/FN study yet.",
            "- RTL-SDR Blog V4 is not a native 2.4/5.8 GHz solution; high-band paths remain conversion/synthetic until a real front-end is qualified.",
            "- Meshtastic RX remains a conservative spool/integration path.",
            "- High-g / line-charge reference sims destroy COTS Pi stacks - that result is a physics boundary, not a shipping promise.",
            "",
            "## Machine-readable artifacts",
            "",
            "| File | Contents |",
            "|------|----------|",
            "| `summary.json` | Gate rollup |",
            "| `pytest-junit.xml` | Pytest JUnit |",
            "| `coverage.xml` | Coverage for the measured include set |",
            "| `defense-readiness-sentry.json` | Full audit (local paths sanitized) |",
            "| `mypy.txt` / `simulation.txt` / `build_readiness.txt` / `audit.txt` | Gate logs |",
            "",
            "## Reproduce",
            "",
            "```bash",
            "python scripts/collect_ci_reports.py",
            "python scripts/publish_results.py",
            "```",
            "",
            "CI also uploads `sentry-ci-reports-<run_id>` on every green Actions run.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    if not (CI_DIR / "summary.json").exists():
        raise SystemExit("missing validation/reports/ci/summary.json - run collect_ci_reports.py first")

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

    cov = OUT / "coverage.xml"
    if cov.exists():
        try:
            root = ET.parse(cov).getroot()
            for elem in root.iter():
                for attr in ("filename", "name"):
                    if attr in elem.attrib:
                        elem.attrib[attr] = elem.attrib[attr].replace("\\", "/")
                        if "src/sentry" in elem.attrib[attr]:
                            elem.attrib[attr] = elem.attrib[attr].split("src/sentry", 1)[-1]
                            if not elem.attrib[attr].startswith("src/"):
                                elem.attrib[attr] = "src/sentry" + elem.attrib[attr]
            ET.ElementTree(root).write(cov, encoding="utf-8", xml_declaration=True)
        except ET.ParseError:
            pass

    html_dir = OUT / "coverage_html"
    if html_dir.exists():
        shutil.rmtree(html_dir)

    print(f"published -> {OUT}")
    print(f"all_passed={summary.get('all_passed')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
