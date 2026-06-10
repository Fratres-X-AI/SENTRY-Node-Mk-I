#!/usr/bin/env python3
"""RunPod GPU validation sweep for DARKSPACE.

This script is intended to run from the DARKSPACE repository root on a RunPod
GPU instance. It bootstraps CUDA dependencies, runs the adversarial harness,
executes the extended Neural Mirror red-team corpus, validates SQLite state,
signs the final report, and sanitizes transient caches.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_DIR = Path("validation/reports")
HARDWARE_MANIFEST = REPORT_DIR / "gpu_hardware_manifest.json"
MASTER_REPORT = REPORT_DIR / "runpod_validation_manifest.json"
DB_PATH = Path(os.environ.get("DARKSPACE_DB_PATH", "audit_log.db"))

JUDGE_MODEL = "qwen2.5-14b-instruct-4bit"
TRUTH_DATASET = Path("tests/real_2026_training_dataset.jsonl")
NEURAL_SAMPLES = 220
RTX4090_TOTAL_VRAM_GB = 24.0
RTX4090_GPU_MEMORY_UTILIZATION = 0.75
RTX4090_RESERVED_VRAM_GB = RTX4090_TOTAL_VRAM_GB * (1.0 - RTX4090_GPU_MEMORY_UTILIZATION)
RTX4090_MAX_CONTEXT_TOKENS = 16_384
RTX4090_MAX_OBSERVED_VRAM_GB = 20.0
BASELINE_SOURCE = Path(os.environ.get("DARKSPACE_APPROVED_PROMPTS", "approved_prompts.txt"))
BASELINE_OUTPUT = Path(os.environ.get("DARKSPACE_BASELINE_PATH", "config/baseline.npy"))

REQUIRED_TABLES = {
    "threat_log": """
        CREATE TABLE IF NOT EXISTS threat_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_ip TEXT,
            threat_type TEXT,
            description TEXT,
            risk_score REAL DEFAULT 0,
            hmac_sig TEXT
        )
    """,
    "prompt_log": """
        CREATE TABLE IF NOT EXISTS prompt_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            input_hash TEXT,
            status TEXT,
            matched_pattern TEXT,
            risk_score REAL DEFAULT 0
        )
    """,
    "ghost_log": """
        CREATE TABLE IF NOT EXISTS ghost_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            iface TEXT,
            metric TEXT,
            value REAL,
            flag TEXT
        )
    """,
    "whisper_log": """
        CREATE TABLE IF NOT EXISTS whisper_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            entropy REAL,
            bigram_ent REAL,
            verdict TEXT,
            text_len INTEGER
        )
    """,
    "mirror_results": """
        CREATE TABLE IF NOT EXISTS mirror_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            sample_id TEXT,
            category TEXT,
            expected TEXT,
            verdict TEXT,
            correct INTEGER,
            detail TEXT
        )
    """,
    "mimicry_log": """
        CREATE TABLE IF NOT EXISTS mimicry_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            baseline_text TEXT,
            test_text TEXT,
            drift_score REAL,
            threshold REAL,
            flagged INTEGER DEFAULT 0
        )
    """,
    "vault_events": """
        CREATE TABLE IF NOT EXISTS vault_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            trigger_alert INTEGER,
            action TEXT,
            mock_key_id TEXT,
            result TEXT
        )
    """,
    "vuln_log": """
        CREATE TABLE IF NOT EXISTS vuln_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cve_id TEXT UNIQUE,
            description TEXT,
            severity TEXT,
            cvss_score REAL,
            published_at TEXT,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "vuln_correlation": """
        CREATE TABLE IF NOT EXISTS vuln_correlation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            cve_id TEXT,
            threat_log_id INTEGER,
            note TEXT
        )
    """,
    "security_metrics": """
        CREATE TABLE IF NOT EXISTS security_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            metric_unit TEXT,
            module TEXT,
            correlation_id TEXT,
            metadata_json TEXT
        )
    """,
    "mesh_inbox": """
        CREATE TABLE IF NOT EXISTS mesh_inbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            peer_url TEXT,
            peer_fingerprint TEXT,
            payload TEXT,
            sig_valid INTEGER DEFAULT 0,
            attest_valid INTEGER DEFAULT 0
        )
    """,
}


class SweepError(RuntimeError):
    """Raised when a validation gate fails."""


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    elapsed_s: float
    peak_gpu_memory_mb: int | None = None


def configure_logging() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(REPORT_DIR / "runpod_validation_sweep.log", encoding="utf-8"),
        ],
    )


def run_command(
    command: list[str],
    *,
    check: bool = True,
    env: dict[str, str] | None = None,
    monitor_gpu: bool = False,
) -> CommandResult:
    logging.info("running: %s", " ".join(command))
    stop_event = threading.Event()
    peak_gpu_memory_mb: list[int | None] = [None]
    monitor: threading.Thread | None = None
    if monitor_gpu:
        monitor = threading.Thread(target=_poll_gpu_memory, args=(stop_event, peak_gpu_memory_mb), daemon=True)
        monitor.start()
    start = time.perf_counter()
    try:
        proc = subprocess.run(command, text=True, capture_output=True, env=env)
    finally:
        stop_event.set()
        if monitor is not None:
            monitor.join(timeout=3.0)
    elapsed = time.perf_counter() - start
    result = CommandResult(command, proc.returncode, proc.stdout, proc.stderr, elapsed, peak_gpu_memory_mb[0])
    if proc.stdout:
        logging.info("stdout tail:\n%s", proc.stdout[-4000:])
    if proc.stderr:
        logging.info("stderr tail:\n%s", proc.stderr[-4000:])
    if check and proc.returncode != 0:
        raise SweepError(f"command failed ({proc.returncode}): {' '.join(command)}")
    if monitor_gpu and result.peak_gpu_memory_mb is not None:
        peak_gb = result.peak_gpu_memory_mb / 1024.0
        logging.info("observed peak GPU memory: %.2f GB", peak_gb)
        if peak_gb > RTX4090_MAX_OBSERVED_VRAM_GB:
            raise SweepError(f"GPU VRAM peak exceeded RTX 4090 gate: {peak_gb:.2f}GB > {RTX4090_MAX_OBSERVED_VRAM_GB:.2f}GB")
    return result


def _poll_gpu_memory(stop_event: threading.Event, peak_out: list[int | None]) -> None:
    while not stop_event.is_set():
        try:
            proc = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                text=True,
                capture_output=True,
                timeout=2,
            )
            if proc.returncode == 0:
                values = [int(line.strip()) for line in proc.stdout.splitlines() if line.strip().isdigit()]
                if values:
                    peak = max(values)
                    peak_out[0] = peak if peak_out[0] is None else max(peak_out[0], peak)
        except Exception:
            pass
        stop_event.wait(1.0)


def configure_rtx4090_profile() -> dict[str, Any]:
    """Set conservative 24GB RTX 4090 runtime defaults for vLLM/HF loaders."""
    vllm_args = (
        f"--quantization awq --gpu-memory-utilization {RTX4090_GPU_MEMORY_UTILIZATION:.2f} "
        f"--max-model-len {RTX4090_MAX_CONTEXT_TOKENS} "
        "--max-num-batched-tokens 4096 --dtype auto --tensor-parallel-size 1 "
        "--enable-chunked-prefill"
    )
    defaults = {
        "DARKSPACE_VLLM_MODEL_ID": "Qwen/Qwen2.5-14B-Instruct-AWQ",
        "DARKSPACE_GATE_MODEL": "Qwen/Qwen2.5-14B-Instruct-AWQ",
        "DARKSPACE_VLLM_EXTRA_ARGS": vllm_args,
        "DARKSPACE_MAX_CONTEXT_TOKENS": str(RTX4090_MAX_CONTEXT_TOKENS),
        "DARKSPACE_CONTEXT_STRESS_MAX_TOKENS": str(RTX4090_MAX_CONTEXT_TOKENS),
        "VLLM_ATTENTION_BACKEND": "FLASH_ATTN",
        "VLLM_USE_FLASH_ATTN": "1",
        "FLASH_ATTENTION_FORCE": "1",
        "TRANSFORMERS_ATTENTION_IMPLEMENTATION": "flash_attention_2",
        "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True,max_split_size_mb:128",
        "TOKENIZERS_PARALLELISM": "false",
    }
    applied: dict[str, str] = {}
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
        applied[key] = os.environ[key]
    return {
        "hardware_profile": "rtx4090_24gb",
        "total_vram_gb": RTX4090_TOTAL_VRAM_GB,
        "gpu_memory_utilization": RTX4090_GPU_MEMORY_UTILIZATION,
        "reserved_vram_gb": RTX4090_RESERVED_VRAM_GB,
        "max_context_tokens": RTX4090_MAX_CONTEXT_TOKENS,
        "max_observed_vram_gate_gb": RTX4090_MAX_OBSERVED_VRAM_GB,
        "env": applied,
    }


def bootstrap_environment(skip_setup: bool) -> None:
    setup = Path("setup_pod_gpu.sh")
    if not setup.exists():
        raise SweepError("setup_pod_gpu.sh not found; run from DARKSPACE repository root")
    if skip_setup:
        logging.info("skipping setup_pod_gpu.sh by request")
        return
    run_command(["bash", "-lc", "chmod +x setup_pod_gpu.sh && ./setup_pod_gpu.sh"])


def collect_gpu_manifest() -> dict[str, Any]:
    code = r"""
import json
import torch

payload = {
    "torch_version": torch.__version__,
    "cuda_available": torch.cuda.is_available(),
    "cuda_version": torch.version.cuda,
    "device_count": torch.cuda.device_count(),
    "devices": [],
}
for idx in range(torch.cuda.device_count()):
    props = torch.cuda.get_device_properties(idx)
    free, total = torch.cuda.mem_get_info(idx)
    payload["devices"].append({
        "index": idx,
        "name": torch.cuda.get_device_name(idx),
        "capability": list(torch.cuda.get_device_capability(idx)),
        "multiprocessor_count": props.multi_processor_count,
        "total_memory_bytes": int(total),
        "free_memory_bytes": int(free),
    })
print(json.dumps(payload))
"""
    result = run_command([sys.executable, "-c", code])
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    if not payload.get("cuda_available") or int(payload.get("device_count", 0)) < 1:
        raise SweepError("CUDA is not available in this RunPod runtime")
    for device in payload.get("devices", []):
        total_gb = float(device.get("total_memory_bytes", 0)) / 1_000_000_000.0
        if total_gb < 22.0:
            raise SweepError(f"RTX 4090 profile requires ~24GB VRAM, got {total_gb:.1f}GB on {device.get('name')}")
    HARDWARE_MANIFEST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def parse_harness_metrics(stdout: str, results_file: Path = Path("test_results.json")) -> dict[str, Any]:
    if results_file.exists():
        data = json.loads(results_file.read_text(encoding="utf-8"))
        summary = data.get("summary", {})
        return {
            "accuracy": float(summary.get("accuracy", 0.0)),
            "fpr": float(summary.get("fpr", 100.0)),
            "fnr": float(summary.get("fnr", 100.0)),
            "avg_latency_ms": float(summary.get("avg_latency_ms", 0.0)),
            "results_file": str(results_file),
        }

    patterns = {
        "accuracy": r"Correct:\s+\d+\s+\(([\d.]+)%\)",
        "fpr": r"False Positive Rate.*?:\s+([\d.]+)%",
        "fnr": r"False Negative Rate.*?:\s+([\d.]+)%",
        "avg_latency_ms": r"Average latency:\s+([\d.]+)\s*ms",
    }
    metrics: dict[str, Any] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, stdout)
        if match:
            metrics[key] = float(match.group(1))
    missing = sorted(set(patterns) - set(metrics))
    if missing:
        raise SweepError(f"could not parse harness metrics: {missing}")
    return metrics


def run_adversarial_harness() -> dict[str, Any]:
    if not TRUTH_DATASET.exists():
        raise SweepError(f"truth dataset missing: {TRUTH_DATASET}")
    result = run_command(
        [
            sys.executable,
            "test_harness.py",
            "--judge",
            JUDGE_MODEL,
            "--dataset",
            str(TRUTH_DATASET),
        ],
        monitor_gpu=True,
    )
    metrics = parse_harness_metrics(result.stdout)
    if metrics["accuracy"] < 75.0:
        raise SweepError(f"accuracy below gate: {metrics['accuracy']}% < 75%")
    if metrics["fnr"] != 0.0:
        raise SweepError(f"false negative rate must be 0.0%, got {metrics['fnr']}%")
    metrics["elapsed_s"] = result.elapsed_s
    metrics["peak_gpu_memory_mb"] = result.peak_gpu_memory_mb
    return metrics


def run_quality_gates(skip_quality: bool) -> dict[str, Any]:
    if skip_quality:
        return {"skipped": True}
    pytest_cmd = [sys.executable, "-m", "pytest", "tests", "--cov=.", "--cov-fail-under=100", "-q"]
    mypy_cmd = [sys.executable, "-m", "mypy", "."]
    pytest_result = run_command(pytest_cmd)
    mypy_result = run_command(mypy_cmd)
    return {
        "skipped": False,
        "pytest_elapsed_s": pytest_result.elapsed_s,
        "mypy_elapsed_s": mypy_result.elapsed_s,
    }


def run_neural_mirror() -> dict[str, Any]:
    before = table_count("mirror_results")
    result = run_command(
        [sys.executable, "neural_mirror.py", "--profile", "extended", "--samples", str(NEURAL_SAMPLES)],
        monitor_gpu=True,
    )
    after = table_count("mirror_results")
    inserted = after - before
    if inserted < NEURAL_SAMPLES:
        raise SweepError(f"neural_mirror wrote {inserted}/{NEURAL_SAMPLES} mirror_results rows")
    return {
        "samples_requested": NEURAL_SAMPLES,
        "rows_inserted": inserted,
        "elapsed_s": result.elapsed_s,
        "peak_gpu_memory_mb": result.peak_gpu_memory_mb,
    }


def export_baseline_float16() -> dict[str, Any]:
    """Export approved prompts to a compact float16 baseline matrix for Pi deployment."""
    if not BASELINE_SOURCE.exists():
        return {
            "status": "skipped",
            "reason": f"{BASELINE_SOURCE} not found",
            "source": str(BASELINE_SOURCE),
            "output": str(BASELINE_OUTPUT),
        }

    prompts = [line.strip() for line in BASELINE_SOURCE.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
    if not prompts:
        return {"status": "skipped", "reason": "approved prompt file is empty", "source": str(BASELINE_SOURCE)}

    try:
        import numpy as np
    except ImportError as exc:
        raise SweepError("numpy is required to export baseline.npy") from exc

    vectors: Any
    method: str
    try:
        from sentence_transformers import SentenceTransformer

        model_name = os.environ.get("DARKSPACE_BASELINE_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        model = SentenceTransformer(model_name)
        vectors = model.encode(prompts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
        method = f"sentence_transformers:{model_name}"
    except Exception as exc:
        logging.warning("embedding model unavailable; using deterministic hashing baseline: %s", exc)
        vectors = _hash_prompt_vectors(prompts)
        method = "deterministic_hash_fallback"

    BASELINE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    arr = np.asarray(vectors, dtype=np.float16)
    np.save(BASELINE_OUTPUT, arr)
    return {
        "status": "written",
        "source": str(BASELINE_SOURCE),
        "output": str(BASELINE_OUTPUT),
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "method": method,
        "bytes": BASELINE_OUTPUT.stat().st_size,
    }


def _hash_prompt_vectors(prompts: list[str], dims: int = 384) -> list[list[float]]:
    rows: list[list[float]] = []
    for prompt in prompts:
        digest = hashlib.sha256(prompt.encode("utf-8")).digest()
        values = []
        while len(values) < dims:
            digest = hashlib.sha256(digest).digest()
            values.extend((byte / 127.5) - 1.0 for byte in digest)
        rows.append(values[:dims])
    return rows


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_core_tables() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True) if DB_PATH.parent != Path(".") else None
    with db_connect() as conn:
        for ddl in REQUIRED_TABLES.values():
            conn.execute(ddl)
        conn.commit()


def table_count(table: str) -> int:
    ensure_core_tables()
    with db_connect() as conn:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def sqlite_integrity_report() -> dict[str, Any]:
    ensure_core_tables()
    with db_connect() as conn:
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        tables: dict[str, int] = {}
        for table in REQUIRED_TABLES:
            tables[table] = int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    if integrity.lower() != "ok":
        raise SweepError(f"SQLite integrity_check failed: {integrity}")
    if tables["mirror_results"] < NEURAL_SAMPLES:
        raise SweepError("mirror_results row count below required extended sweep size")
    return {"db_path": str(DB_PATH), "integrity_check": integrity, "tables": tables}


def sign_payload(payload: dict[str, Any]) -> str:
    secret = os.environ.get("DARKSPACE_HMAC_SECRET")
    if not secret:
        raise SweepError("DARKSPACE_HMAC_SECRET is required to sign validation manifest")
    return hmac.new(secret.encode("utf-8"), canonical_json(payload), hashlib.sha256).hexdigest()


def canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_signed_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    unsigned = dict(payload)
    signature = sign_payload(unsigned)
    signed = {
        **unsigned,
        "signature": {
            "alg": "HMAC-SHA256",
            "env_key": "DARKSPACE_HMAC_SECRET",
            "hex": signature,
        },
    }
    MASTER_REPORT.write_text(json.dumps(signed, indent=2) + "\n", encoding="utf-8")
    return signed


def sanitize_transient_storage(paths: list[Path]) -> None:
    for path in paths:
        if not path.exists():
            continue
        try:
            if path.is_file():
                path.write_bytes(b"\x00" * path.stat().st_size)
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            logging.info("sanitized transient path: %s", path)
        except OSError as exc:
            logging.warning("failed to sanitize %s: %s", path, exc)


def run_sweep(args: argparse.Namespace) -> dict[str, Any]:
    configure_logging()
    started = datetime.now(timezone.utc).isoformat()
    tmpdir = Path(tempfile.mkdtemp(prefix="darkspace-runpod-"))
    os.environ.setdefault("DARKSPACE_DB_PATH", str(DB_PATH))
    rtx4090_profile = configure_rtx4090_profile()

    try:
        bootstrap_environment(skip_setup=args.skip_setup)
        hardware = collect_gpu_manifest()
        quality = run_quality_gates(skip_quality=args.skip_quality)
        adversarial = run_adversarial_harness()
        mirror = run_neural_mirror()
        baseline = export_baseline_float16()
        sqlite_report = sqlite_integrity_report()
        payload = {
            "schema": "darkspace_runpod_validation.v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "started_at": started,
            "repo_root": str(Path.cwd()),
            "judge_model": JUDGE_MODEL,
            "truth_dataset": str(TRUTH_DATASET),
            "rtx4090_optimization_profile": rtx4090_profile,
            "gpu_hardware_manifest": hardware,
            "quality_gates": quality,
            "adversarial_harness": adversarial,
            "neural_mirror": mirror,
            "baseline_export": baseline,
            "sqlite_integrity": sqlite_report,
            "status": "PASS",
        }
        signed = write_signed_manifest(payload)
        logging.info("validation PASS: %s", MASTER_REPORT)
        return signed
    except Exception as exc:
        failure_payload = {
            "schema": "darkspace_runpod_validation.v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "started_at": started,
            "repo_root": str(Path.cwd()),
            "status": "FAIL",
            "error": repr(exc),
        }
        try:
            write_signed_manifest(failure_payload)
        except Exception:
            logging.exception("failed to sign failure manifest")
        logging.exception("validation FAILED")
        raise
    finally:
        sanitize_transient_storage(
            [
                tmpdir,
                Path(".pytest_cache"),
                Path(".mypy_cache"),
                Path("__pycache__"),
                Path("test_results.json") if args.remove_test_results else Path("__do_not_remove__"),
            ]
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RunPod DARKSPACE GPU validation sweep")
    parser.add_argument("--skip-setup", action="store_true", help="Skip setup_pod_gpu.sh when the pod image is already prepared")
    parser.add_argument("--skip-quality", action="store_true", help="Skip pytest/mypy quality gates")
    parser.add_argument(
        "--remove-test-results",
        action="store_true",
        help="Remove test_results.json after it has been folded into the signed manifest",
    )
    return parser.parse_args()


def main() -> int:
    try:
        run_sweep(parse_args())
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
