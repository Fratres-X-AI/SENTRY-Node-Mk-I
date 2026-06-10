"""Visual motion score adapter (OpenCV optional, stub fallback)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sentry.hardware import adapter_status, clamp01

LOG = logging.getLogger("SENTRY")


@dataclass
class VisualConfig:
    camera_index: int = 0
    frame_width: int = 160
    frame_height: int = 120


def probe(config: VisualConfig | None = None) -> dict[str, Any]:
    cfg = config or VisualConfig()
    try:
        import cv2
    except ImportError:
        return adapter_status("visual", False, "opencv-python-headless not installed")
    cap = cv2.VideoCapture(cfg.camera_index)
    if not cap.isOpened():
        cap.release()
        return adapter_status("visual", False, f"camera {cfg.camera_index} not opened")
    ok, _ = cap.read()
    cap.release()
    if not ok:
        return adapter_status("visual", False, "camera read failed")
    return adapter_status("visual", True, f"camera_index={cfg.camera_index}")


class VisualAdapter:
    """Lightweight motion score from consecutive frames."""

    def __init__(self, config: VisualConfig | None = None) -> None:
        self.config = config or VisualConfig()
        self._cap: Any | None = None
        self._prev: Any | None = None
        self._cv2: Any | None = None
        self._available = False
        try:
            import cv2

            cap = cv2.VideoCapture(self.config.camera_index)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.frame_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.frame_height)
            if cap.isOpened():
                self._cap = cap
                self._cv2 = cv2
                self._available = True
        except ImportError:
            LOG.info("SENTRY visual adapter unavailable — install opencv-python-headless")

    @property
    def available(self) -> bool:
        return self._available and self._cap is not None

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def read(self) -> float:
        if not self.available or self._cap is None:
            return 0.0
        ok, frame = self._cap.read()
        if not ok:
            return 0.0
        cv2 = self._cv2
        assert cv2 is not None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self._prev is None:
            self._prev = gray
            return 0.0
        diff = cv2.absdiff(gray, self._prev)
        self._prev = gray
        mean_diff = float(diff.mean()) / 255.0
        return clamp01(mean_diff * 4.0)
