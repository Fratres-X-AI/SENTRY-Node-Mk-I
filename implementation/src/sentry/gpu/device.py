"""CUDA device selection for SENTRY dev/simulation (not Pi field)."""

from __future__ import annotations

import os


def cuda_available() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except ImportError:
        return False


def get_device(force_gpu: bool = False):
    import torch

    if force_gpu or os.environ.get("SENTRY_FORCE_GPU", "").lower() in ("1", "true", "yes"):
        if not torch.cuda.is_available():
            raise RuntimeError("SENTRY_FORCE_GPU set but CUDA unavailable")
        return torch.device("cuda")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def require_cuda() -> "torch.device":
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required for GPU melt — Pi field uses CPU only")
    torch.cuda.set_device(0)
    return torch.device("cuda")
