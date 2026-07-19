"""Run local CI gates and write machine-readable reports under validation/reports/ci/."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_DIR = ROOT / "validation" / "reports" / "ci"
IMPL = ROOT / "implementation"


def _run(cmd: list[str], *, cwd: Path, log_name: str) -> int:
    CI_DIR.mkdir(parents=True, exist_ok=True)
    log_path = CI_DIR / log_name
    print(f"$ {' '.join(cmd)}", flush=True)
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    log_path.write_text(text, encoding="utf-8")
    print(text[-4000:] if len(text) > 4000 else text, flush=True)
    return proc.returncode


def _parse_pytest_junit(path: Path) -> dict:
    if not path.exists():
        return {"tests": 0, "passed": 0, "failures": 0, "errors": 0, "skipped": 0, "time_s": 0.0}
    root = ET.parse(path).getroot()
    # pytest may emit <testsuites><testsuite> or bare <testsuite>
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
        return {"line_rate": 0.0, "lines_valid": 0, "lines_covered": 0}
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


def _parse_mypy(log_path: Path, exit_code: int) -> dict:
    text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    # "Success: no issues found in 42 source files"
    m = re.search(r"no issues found in (\d+) source files", text)
    files = int(m.group(1)) if m else 0
    err_count = len(re.findall(r"error:", text))
    return {"passed": exit_code == 0, "source_files": files, "errors": err_count}


def main() -> int:
    CI_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")

    gates: dict[str, dict] = {}

    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "--cov=sentry",
        "--cov-fail-under=100",
        "--cov-report=term-missing",
        f"--cov-report=xml:{CI_DIR / 'coverage.xml'}",
        f"--cov-report=html:{CI_DIR / 'coverage_html'}",
        f"--junitxml={CI_DIR / 'pytest-junit.xml'}",
        "-q",
        "-k",
        "not gpu",
    ]
    pytest_exit = subprocess.run(pytest_cmd, cwd=str(IMPL), env=env).returncode
    # also save a short log via re-run capture is heavy; parse artifacts instead
    pytest_stats = _parse_pytest_junit(CI_DIR / "pytest-junit.xml")
    gates["pytest"] = {
        "exit_code": pytest_exit,
        "ok": pytest_exit == 0,
        **pytest_stats,
        "passed_count": pytest_stats["passed"],
        "coverage": _parse_coverage_xml(CI_DIR / "coverage.xml"),
    }

    mypy_exit = _run([sys.executable, "-m", "mypy", "src/sentry"], cwd=IMPL, log_name="mypy.txt")
    gates["mypy"] = {"exit_code": mypy_exit, **_parse_mypy(CI_DIR / "mypy.txt", mypy_exit)}

    sim_exit = _run(
        [sys.executable, "validation/vv/run_sentry_simulation.py"],
        cwd=ROOT,
        log_name="simulation.txt",
    )
    gates["simulation"] = {"exit_code": sim_exit, "passed": sim_exit == 0}

    build_exit = _run(
        [sys.executable, "validation/build_readiness.py"],
        cwd=ROOT,
        log_name="build_readiness.txt",
    )
    gates["build_readiness"] = {"exit_code": build_exit, "passed": build_exit == 0}

    audit_exit = _run(
        [sys.executable, "run_complete_audit.py"],
        cwd=ROOT,
        log_name="audit.txt",
    )
    audit_json = ROOT / "validation" / "reports" / "defense-readiness-sentry.json"
    audit_payload: dict = {}
    if audit_json.exists():
        audit_payload = json.loads(audit_json.read_text(encoding="utf-8"))
        # copy into ci dir for artifact packaging
        (CI_DIR / "defense-readiness-sentry.json").write_text(
            json.dumps(audit_payload, indent=2) + "\n", encoding="utf-8"
        )
    scenarios = audit_payload.get("scenarios") or audit_payload.get("simulation_scenarios") or []
    if isinstance(scenarios, dict):
        scenario_rows = [
            {"name": k, "status": v.get("status", "UNKNOWN") if isinstance(v, dict) else str(v)}
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
    gates["audit"] = {
        "exit_code": audit_exit,
        "passed": audit_exit == 0,
        "overall": audit_payload.get("overall") or audit_payload.get("status"),
        "scenarios": scenario_rows,
        "failure_modes_overall": failure_modes.get("overall"),
        "tamper_detection": (audit_payload.get("tamper_detection") or {}).get("passed"),
    }

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "all_passed": all(
            bool(g.get("ok") if "ok" in g else g.get("passed") or g.get("exit_code") == 0)
            for g in (
                gates["pytest"],
                gates["mypy"],
                gates["simulation"],
                gates["build_readiness"],
                gates["audit"],
            )
        ),
        "gates": gates,
    }
    (CI_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"all_passed": summary["all_passed"], "pytest": gates["pytest"]}, indent=2))
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
