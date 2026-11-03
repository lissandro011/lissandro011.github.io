import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe no instalados")


def make_video(path: Path, *args: str) -> bytes:
    """Genera un video de prueba con ffmpeg (fuentes sintéticas lavfi)."""
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args, str(path)],
        check=True,
        timeout=120,
    )
    return path.read_bytes()
