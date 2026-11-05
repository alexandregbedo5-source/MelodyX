"""MELODYX — B2: Audio decoding and preprocessing.

Converts uploaded audio files to WAV PCM (22 050 Hz, mono) via ffmpeg
and performs basic silence detection using librosa RMS energy.
"""

import logging
import os
import subprocess
from pathlib import Path

import librosa
import numpy as np

logger = logging.getLogger(__name__)

_SAMPLE_RATE: int = 22050
_CHANNELS: int = 1
_SILENCE_RMS_THRESHOLD: float = 0.001


def decode_audio(input_path: str, output_dir: str) -> dict:
    """Decode any audio file to WAV PCM via ffmpeg.

    Args:
        input_path: Path to the source audio file.
        output_dir: Directory where the converted WAV will be written.

    Returns:
        A dict with keys ``wav_path``, ``duration_seconds``, ``sample_rate``,
        ``channels``, and ``warnings``.

    Raises:
        ValueError: If ffmpeg exits with a non-zero return code.
        FileNotFoundError: If *input_path* does not exist.
    """
    src = Path(input_path)
    if not src.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    os.makedirs(output_dir, exist_ok=True)
    wav_name = f"{src.stem}_converted.wav"
    wav_path = str(Path(output_dir) / wav_name)

    warnings: list[str] = []

    # ---- ffmpeg conversion ------------------------------------------------
    cmd = [
        "ffmpeg",
        "-y",                # overwrite without asking
        "-i", input_path,
        "-ar", str(_SAMPLE_RATE),
        "-ac", str(_CHANNELS),
        "-f", "wav",
        wav_path,
    ]

    logger.info("Running ffmpeg: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        stderr_snippet = (result.stderr or "")[-500:]
        raise ValueError(
            f"ffmpeg failed (exit code {result.returncode}): {stderr_snippet}"
        )

    if not Path(wav_path).is_file():
        raise ValueError("ffmpeg did not produce an output file")

    # ---- Load & inspect ----------------------------------------------------
    y, sr = librosa.load(wav_path, sr=_SAMPLE_RATE, mono=True)
    duration: float = float(librosa.get_duration(y=y, sr=sr))

    # ---- Silence detection -------------------------------------------------
    rms = librosa.feature.rms(y=y)[0]
    mean_rms: float = float(np.mean(rms))
    if mean_rms < _SILENCE_RMS_THRESHOLD:
        warnings.append("silent_audio")
        logger.warning("Audio appears silent (mean RMS=%.6f)", mean_rms)

    logger.info(
        "Decoded %s → %s  (%.2f s, %d Hz, %d ch)",
        input_path, wav_path, duration, sr, _CHANNELS,
    )

    return {
        "wav_path": wav_path,
        "duration_seconds": round(duration, 4),
        "sample_rate": sr,
        "channels": _CHANNELS,
        "warnings": warnings,
    }
