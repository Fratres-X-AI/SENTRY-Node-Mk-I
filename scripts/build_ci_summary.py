"""Build validation/reports/ci/summary.json from pytest/coverage/mypy/audit artifacts."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_DIR = ROOT / "validation" / "reports" / "ci"


def _parse_pytest_junit(path: Path) -> dict:
    if not path.exists():
        return {"tests": 0, "passed": 0, "failures": 0, "errors": 0, "skipped": 0, "time_s": 0.0}
    root = ET.parse(path).getroot()
    suites = root.findall("testsuite")
    if root.tag == "testsuite":
        suites = [root]
    tests = failures = errors = skipped = 0
    time_s = 0.0
    for suite in suites:
        tests += int(suite.attrib.get("tests", 0))
        failures += int(suite.attrib.get("failures", 0))
        errors += int(suite.attrib.get("errors", 0))
        skipped += int(suite.attrib.get("skipped", 0))
        time_s += float(suite.attrib.get("time", 0) or 0)
    passed = max(0, tests - failures - errors - skipped)
    return {
        "tests": tests,
        "passed": passed,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "time_s": round(time_s, 3),
    }


def _parse_coverage_xml(path: Path) -> dict:
    if not path.exists():
        return {"line_rate": 0.0, "lines_valid": 0, "lines_covered": 0, "packages": []}
    root = ET.parse(path).getroot()
    rate = float(root.attrib.get("line-rate", 0) or 0)
    valid = int(root.attrib.get("lines-valid", 0) or 0)
    covered = int(root.attrib.get("lines-covered", 0) or 0)
    packages: list[dict] = []
    for pkg in root.findall(".//package"):
        name = pkg.attrib.get("name") or "(root)"
        pkg_rate = float(pkg.attrib.get("line-rate", 0) or 0)
        packages.append({"name": name, "line_rate_pct": round(pkg_rate * 100, 2)})
    packages.sort(key=lambda p: p["name"])
    return {
        "line_rate": round(rate * 100, 2),
        "lines_valid": valid,
        "lines_covered": covered,
        "packages": packages,
    }


def _parse_mypy(log_path: Path) -> dict:
    text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    m = re.search(r"no issues found in (\d+) source files", text)
    files = int(m.group(1)) if m else 0
    err_count = len(re.findall(r"error:", text))
    passed = "Success: no issues found" in text or (files > 0 and err_count == 0)
    return {"passed": passed, "source_files": files, "errors": err_count}


def _log_passed(name: str) -> bool:
    path = CI_DIR / name
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    # Prefer explicit FAIL signals over PASS noise.
    if "traceback" in text or "error:" in text and "no issues found" not in text:
        # mypy handled separately; for other logs look for exit markers in audit overall
        pass
    if "overall\": \"fail\"" in text or "status\": \"fail\"" in text:
        return False
    return True


def main() -> int:
    CI_DIR.mkdir(parents=True, exist_ok=True)
    pytest_stats = _parse_pytest_junit(CI_DIR / "pytest-junit.xml")
    coverage = _parse_coverage_xml(CI_DIR / "coverage.xml")
    mypy = _parse_mypy(CI_DIR / "mypy.txt")

    audit_path = CI_DIR / "defense-readiness-sentry.json"
    if not audit_path.exists():
        alt = ROOT / "validation" / "reports" / "defense-readiness-sentry.json"
        if alt.exists():
            audit_path.write_text(alt.read_text(encoding="utf-8"), encoding="utf-8")
    audit_payload: dict = {}
    if audit_path.exists():
        audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))

    scenarios = audit_payload.get("scenarios") or []
    if isinstance(scenarios, dict):
        scenario_rows = [
            {"name": k, "status": (v.get("status") if isinstance(v, dict) else str(v))}
            for k, v in scenarios.items()
        ]
    else:
        scenario_rows = [
            {
                "name": s.get("scenario", s.get("name", "unknown")),
                "status": s.get("status", "UNKNOWN"),
            }
            for s in scenarios
            if isinstance(s, dict)
        ]

    failure_modes = audit_payload.get("failure_modes") or {}
    overall = str(audit_payload.get("overall") or audit_payload.get("status") or "").upper()
    audit_passed = overall in {"PASS", "PASSED", "OK", "GREEN"} or (
        bool(scenario_rows) and all(str(s.get("status", "")).upper() == "PASS" for s in scenario_rows)
    )

    pytest_ok = (
        pytest_stats["failures"] == 0
        and pytest_stats["errors"] == 0
        and pytest_stats["tests"] > 0
        and coverage.get("line_rate", 0) >= 100.0
    )
    gates = {
        "pytest": {
            **pytest_stats,
            "ok": pytest_ok,
            "passed_count": pytest_stats["passed"],
            "coverage": coverage,
        },
        "mypy": {**mypy, "ok": bool(mypy.get("passed"))},
        "simulation": {
            "ok": (CI_DIR / "simulation.txt").exists()
            and "traceback"
            not in (CI_DIR / "simulation.txt").read_text(encoding="utf-8", errors="replace").lower()
        },
        "build_readiness": {
            "ok": (CI_DIR / "build_readiness.txt").exists()
            and "\"overall\": \"fail\""
            not in (CI_DIR / "build_readiness.txt").read_text(encoding="utf-8", errors="replace").lower()
            and "traceback"
            not in (CI_DIR / "build_readiness.txt").read_text(encoding="utf-8", errors="replace").lower()
        },
        "audit": {
            "ok": audit_passed,
            "passed": audit_passed,
            "overall": overall or None,
            "scenarios": scenario_rows,
            "failure_modes_overall": failure_modes.get("overall"),
            "tamper_detection": (audit_payload.get("tamper_detection") or {}).get("passed"),
        },
    }

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "github-actions" if Path("/github/workspace").exists() else "local",
        "all_passed": all(
            bool(g.get("ok") if "ok" in g else g.get("passed")) for g in gates.values()
        ),
        "gates": gates,
    }
    (CI_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
