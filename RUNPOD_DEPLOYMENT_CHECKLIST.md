# RunPod Deployment Checklist

This checklist runs the heavy DARKSPACE cloud validation sweep on a RunPod pod. The current optimization profile is tuned for a single RTX 4090 with 24GB VRAM. The orchestration entrypoint is:

```bash
python scripts/runpod_validation_sweep.py
```

The script must be run from the DARKSPACE repository root after syncing the project to the pod.

## 1. Pod Requirements

- GPU: RTX 4090 24GB profile, or larger. The sweep fails closed if the detected GPU exposes less than ~22GB VRAM.
- Image: PyTorch CUDA 12.4-capable base image.
- Disk: enough free space for model cache and `qwen2.5-14b-instruct-4bit`.
- Network: direct TCP SSH enabled. Use the "SSH over exposed TCP" endpoint because it supports SCP/SFTP.
- Secrets:
  - `DARKSPACE_HMAC_SECRET`
  - Hugging Face token if the judge model download requires it, usually `HF_TOKEN`.

## 2. Local Sync

From your Windows workstation, use the pod's direct TCP endpoint shown in RunPod. Your current pod screen shows this pattern:

```powershell
scp -P 33353 -i "$env:USERPROFILE\.ssh\id_ed25519" -r "C:\Users\Besn Daddy\Desktop\darkspace-gray-swan-blue-reference" root@157.157.221.29:/workspace/darkspace
```

For this SENTRY workspace artifact only:

```powershell
scp -P 33353 -i "$env:USERPROFILE\.ssh\id_ed25519" "C:\Users\Besn Daddy\Desktop\Sentry\scripts\runpod_validation_sweep.py" root@157.157.221.29:/workspace/darkspace/scripts/runpod_validation_sweep.py
scp -P 33353 -i "$env:USERPROFILE\.ssh\id_ed25519" "C:\Users\Besn Daddy\Desktop\Sentry\RUNPOD_DEPLOYMENT_CHECKLIST.md" root@157.157.221.29:/workspace/darkspace/RUNPOD_DEPLOYMENT_CHECKLIST.md
```

If your pod IP or port changes, copy the fresh values from RunPod's **SSH over exposed TCP** block.

## 3. Connect To The Pod

```powershell
ssh root@157.157.221.29 -p 33353 -i "$env:USERPROFILE\.ssh\id_ed25519"
```

Inside the pod:

```bash
cd /workspace/darkspace
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
```

## 4. Inject Secrets

Use a high-entropy HMAC secret. Do not paste secrets into shell history on shared systems.

```bash
read -s DARKSPACE_HMAC_SECRET
export DARKSPACE_HMAC_SECRET

# Optional, only if Hugging Face model access requires it:
read -s HF_TOKEN
export HF_TOKEN
```

For non-interactive runs:

```bash
export DARKSPACE_HMAC_SECRET="$(python - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
```

## 5. Run The Master Sweep

The script automatically applies the RTX 4090 profile:

```bash
export DARKSPACE_VLLM_MODEL_ID="${DARKSPACE_VLLM_MODEL_ID:-Qwen/Qwen2.5-14B-Instruct-AWQ}"
export DARKSPACE_VLLM_EXTRA_ARGS="${DARKSPACE_VLLM_EXTRA_ARGS:---quantization awq --gpu-memory-utilization 0.75 --max-model-len 16384 --max-num-batched-tokens 4096 --dtype auto --tensor-parallel-size 1 --enable-chunked-prefill}"
export VLLM_ATTENTION_BACKEND="${VLLM_ATTENTION_BACKEND:-FLASH_ATTN}"
export TRANSFORMERS_ATTENTION_IMPLEMENTATION="${TRANSFORMERS_ATTENTION_IMPLEMENTATION:-flash_attention_2}"
```

This leaves roughly 6GB VRAM free for fuzzing, token embedding, and runtime buffers. The sweep records peak GPU memory during the Qwen and Neural Mirror phases and fails if observed memory exceeds 20GB.

Default full lifecycle:

```bash
python scripts/runpod_validation_sweep.py
```

If the pod image is already fully prepared and `setup_pod_gpu.sh` has been run:

```bash
python scripts/runpod_validation_sweep.py --skip-setup
```

The script performs:

- `chmod +x setup_pod_gpu.sh && ./setup_pod_gpu.sh`
- CUDA/PyTorch hardware manifest capture
- `python test_harness.py --judge qwen2.5-14b-instruct-4bit --dataset tests/real_2026_training_dataset.jsonl`
- Accuracy gate: `>=75%`
- FNR gate: exactly `0.0%`
- `python neural_mirror.py --profile extended --samples 220`
- SQLite `PRAGMA integrity_check`
- Integrity checks across 11 core tables
- HMAC-signed master validation manifest
- RTX 4090 VRAM peak tracking
- `baseline.npy` float16 export when `approved_prompts.txt` exists
- Transient cache cleanup

## 6. Expected Artifacts

Artifacts are written under:

```bash
validation/reports/
```

Required outputs:

- `validation/reports/gpu_hardware_manifest.json`
- `validation/reports/runpod_validation_manifest.json`
- `validation/reports/runpod_validation_sweep.log`
- `audit_log.db`
- optional `config/baseline.npy`

The master manifest contains:

- GPU device names, memory, CUDA version, and compute capability
- adversarial harness accuracy/FPR/FNR
- Neural Mirror rows inserted
- SQLite table counts and integrity status
- HMAC-SHA256 signature using `DARKSPACE_HMAC_SECRET`
- RTX 4090 profile values: `gpu_memory_utilization=0.75`, max context `16384`, Flash Attention hints
- baseline export status, shape, dtype, and path

## 7. Verify The Signed Manifest

Inside the pod:

```bash
python - <<'PY'
import hashlib, hmac, json, os
from pathlib import Path

path = Path("validation/reports/runpod_validation_manifest.json")
data = json.loads(path.read_text())
sig = data.pop("signature")
expected = hmac.new(
    os.environ["DARKSPACE_HMAC_SECRET"].encode(),
    json.dumps(data, sort_keys=True, separators=(",", ":")).encode(),
    hashlib.sha256,
).hexdigest()
print("signature_valid=", hmac.compare_digest(expected, sig["hex"]))
print("status=", data["status"])
PY
```

Expected:

```text
signature_valid= True
status= PASS
```

## 8. Retrieve Artifacts

From your Windows workstation:

```powershell
mkdir "C:\Users\Besn Daddy\Desktop\Sentry\validation\runpod_artifacts"

scp -P 33353 -i "$env:USERPROFILE\.ssh\id_ed25519" root@157.157.221.29:/workspace/darkspace/validation/reports/gpu_hardware_manifest.json "C:\Users\Besn Daddy\Desktop\Sentry\validation\runpod_artifacts\"
scp -P 33353 -i "$env:USERPROFILE\.ssh\id_ed25519" root@157.157.221.29:/workspace/darkspace/validation/reports/runpod_validation_manifest.json "C:\Users\Besn Daddy\Desktop\Sentry\validation\runpod_artifacts\"
scp -P 33353 -i "$env:USERPROFILE\.ssh\id_ed25519" root@157.157.221.29:/workspace/darkspace/validation/reports/runpod_validation_sweep.log "C:\Users\Besn Daddy\Desktop\Sentry\validation\runpod_artifacts\"
scp -P 33353 -i "$env:USERPROFILE\.ssh\id_ed25519" root@157.157.221.29:/workspace/darkspace/audit_log.db "C:\Users\Besn Daddy\Desktop\Sentry\validation\runpod_artifacts\"
```

## 9. Secure Cleanup

Inside the pod:

```bash
unset DARKSPACE_HMAC_SECRET HF_TOKEN
rm -rf ~/.cache/huggingface ~/.cache/torch .pytest_cache .mypy_cache __pycache__
history -c || true
```

Then stop or terminate the RunPod instance from the RunPod dashboard.

## 10. Live GPU Monitoring

Use this in a second SSH session during the 220-sample sweep:

```bash
watch -n 1 'nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv'
```

Simple live monitor:

```bash
nvidia-smi -l 1
```

Expected RTX 4090 behavior:

- Model load phase: Qwen 14B AWQ should settle around 11-13GB VRAM.
- Stress matrix: GPU utilization may spike to 100%, but VRAM should stay below 20GB.
- Baseline export: embedding work drops off after `baseline.npy` is written as float16.

For PyTorch-level confirmation:

```bash
python - <<'PY'
import torch
for i in range(torch.cuda.device_count()):
    free, total = torch.cuda.mem_get_info(i)
    print(i, torch.cuda.get_device_name(i), "free_GB=", round(free/1e9, 2), "total_GB=", round(total/1e9, 2))
PY
```
