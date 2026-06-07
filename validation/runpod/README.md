# SENTRY on RunPod

Bootstrap SENTRY validation on a RunPod CPU/GPU instance (e.g. RTX PRO 4500 + 32 vCPU).

## Pods used

### A100 SXM (passive_cyan_rhinoceros) — **recommended for GPU**

| Resource | Value |
|----------|-------|
| GPU | **NVIDIA A100-SXM4-80GB** |
| vCPU | 32 (256 threads visible) |
| RAM | 250 GB+ |
| Workspace | `/workspace/fratres-sentry` |

```bash
ssh root@195.26.233.30 -p 23873 -i ~/.ssh/id_ed25519
ssh 81v17rncnmxnss-64411258@ssh.runpod.io -i ~/.ssh/id_ed25519
```

**A100 MAX completed:** 200k Monte Carlo, 200k-sample GPU acoustic train, 60k mesh alerts — see `runpod-max-summary-a100.json`.

```bash
export SENTRY_WORKERS=200 SENTRY_MASS_SCENARIOS=50000 SENTRY_GPU_TRAIN_SAMPLES=200000
./validation/runpod/run_max.sh
```

### RTX PRO 4500 (corresponding_tomato_silverfish)

Blackwell sm_120 — PyTorch CUDA fallback to CPU. Use A100 for GPU workloads.



## Upload codebase

```bash
scp -P 42910 -i ~/.ssh/id_ed25519 -r "/path/to/Sentry" root@213.173.107.40:/workspace/fratres-sentry
```

## On-pod bootstrap

```bash
cd /workspace/fratres-sentry
chmod +x validation/runpod/*.sh
export SENTRY_ROOT=/workspace/fratres-sentry
export SENTRY_WORKERS=30
export SENTRY_MASS_SCENARIOS=2000
./validation/runpod/bootstrap_sentry.sh
```

## Outputs

| File | Contents |
|------|----------|
| `validation/reports/defense-readiness-sentry.json` | Full audit |
| `validation/reports/runpod-mass-validation.json` | Monte Carlo stats |

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `SENTRY_WORKERS` | vCPU−2 | Parallel Monte Carlo pool |
| `SENTRY_MASS_SCENARIOS` | 2000 | Runs per scenario type |
| `SENTRY_MASS_FRAMES` | 40 | Frames per run |

## Notes

- GPU is optional; mass validation is CPU-bound multiprocessing.
- RTL-SDR packages install for probe parity; no USB dongle on pod.
- 30 GB disk: avoid large CUDA stacks unless training acoustic models.
