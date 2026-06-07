#!/usr/bin/env python3
"""GPU-accelerated synthetic propeller acoustic training + inference benchmark."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "implementation" / "src"))

REPORTS = ROOT / "validation" / "reports"


def main() -> int:
    try:
        import numpy as np
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError as e:
        report = {"codename": "SENTRY", "status": "SKIP", "reason": str(e)}
        out = REPORTS / "runpod-gpu-acoustic.json"
        out.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
        return 0

    device = torch.device("cpu")
    gpu_name = "cpu"
    if torch.cuda.is_available():
        try:
            _ = torch.zeros(1, device="cuda")
            _ = torch.relu(_)
            device = torch.device("cuda")
            gpu_name = torch.cuda.get_device_name(0)
        except RuntimeError:
            gpu_name = f"cpu_fallback (CUDA sm_120 unsupported: {torch.cuda.get_device_name(0)})"
            torch.set_num_threads(int(os.environ.get("SENTRY_TORCH_THREADS", 64)))

    # Synthetic dataset: FFT magnitude vectors with propeller peak at 100-500 Hz
    n_train = int(os.environ.get("SENTRY_GPU_TRAIN_SAMPLES", 100_000))
    n_test = int(os.environ.get("SENTRY_GPU_TEST_SAMPLES", 10_000))
    epochs = int(os.environ.get("SENTRY_GPU_EPOCHS", 15))
    batch_size = int(os.environ.get("SENTRY_GPU_BATCH", 1024))
    n_bins = 256
    sr = 16_000

    def make_batch(n: int):
        X = np.random.randn(n, n_bins).astype(np.float32) * 0.05
        y = np.zeros(n, dtype=np.float32)
        for i in range(n):
            is_prop = np.random.rand() > 0.5
            if is_prop:
                freq = np.random.uniform(100, 500)
                bin_idx = int(freq / (sr / 2) * n_bins) % n_bins
                X[i, bin_idx] += np.random.uniform(0.5, 2.0)
                lo = max(0, bin_idx - 1)
                hi = min(n_bins, bin_idx + 2)
                X[i, lo:hi] += 0.3
                y[i] = 1.0
        return X, y

    X_train, y_train = make_batch(n_train)
    X_test, y_test = make_batch(n_test)

    class PropNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(n_bins, 128),
                nn.ReLU(),
                nn.Linear(128, 64),
                nn.ReLU(),
                nn.Linear(64, 1),
                nn.Sigmoid(),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.net(x).squeeze(-1)

    model = PropNet().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCELoss()

    train_ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train))
    loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=8, pin_memory=True)

    t0 = time.perf_counter()
    model.train()
    for epoch in range(epochs):
        epoch_loss = 0.0
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            opt.step()
            epoch_loss += loss.item() * len(xb)
        if (epoch + 1) % 5 == 0:
            print(f"epoch {epoch+1}/{epochs} loss={epoch_loss/n_train:.4f}")

    train_s = time.perf_counter() - t0

    model.eval()
    with torch.no_grad():
        preds = model(torch.from_numpy(X_test).to(device))
        pred_labels = (preds > 0.5).float()
        acc = (pred_labels == torch.from_numpy(y_test).to(device)).float().mean().item()

    # Throughput benchmark
    bench_x = torch.from_numpy(X_test[:1000]).to(device)
    torch.cuda.synchronize() if device.type == "cuda" else None
    t1 = time.perf_counter()
    with torch.no_grad():
        for _ in range(100):
            model(bench_x)
    if device.type == "cuda":
        torch.cuda.synchronize()
    infer_ms = (time.perf_counter() - t1) / 100 * 1000

    report = {
        "codename": "SENTRY",
        "mode": "gpu_acoustic_propeller_classifier",
        "device": gpu_name,
        "train_samples": n_train,
        "test_samples": n_test,
        "epochs": epochs,
        "train_seconds": round(train_s, 2),
        "test_accuracy": round(acc, 4),
        "inference_ms_per_1000_batch": round(infer_ms, 3),
        "samples_per_second": round(1000 * 100 / (infer_ms / 1000) if infer_ms else 0, 0),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "runpod-gpu-acoustic.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if acc >= 0.85 else 1


if __name__ == "__main__":
    sys.exit(main())
