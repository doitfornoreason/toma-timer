"""Sound notifications for Toma Timer.

Uses whichever system audio player is available (ffplay, mpv, paplay, aplay,
mpg123) rather than bundling a heavy audio library. A default pleasant chime
is synthesised at runtime if no custom sound file is configured.

All playback runs in a daemon thread so it never blocks the GUI.
"""
from __future__ import annotations

import math
import shutil
import struct
import subprocess
import tempfile
import threading
import wave
from pathlib import Path

# Order matters: prefer players that handle mp3/flac/wav transparently.
_PLAYERS = ["ffplay", "mpv", "paplay", "mpg123", "aplay"]


def _find_player() -> str | None:
    for name in _PLAYERS:
        if shutil.which(name):
            return name
    return None


def _synth_default_chime(path: Path) -> None:
    """Synthesise a short two-tone bell chime as a 16-bit WAV."""
    sample_rate = 44100
    duration = 1.2  # seconds
    # Two descending tones (E5 -> A4) with exponential decay envelope.
    freqs = [659.25, 440.0]
    n_samples = int(sample_rate * duration)
    samples = [0.0] * n_samples
    for i, freq in enumerate(freqs):
        start = i * (n_samples // 2)
        n = n_samples - start
        for j in range(n):
            t = j / sample_rate
            # Decay envelope
            env = math.exp(-3.0 * t)
            samples[start + j] += env * math.sin(2 * math.pi * freq * t)

    # Normalise to 0.7 max amplitude
    peak = max(abs(s) for s in samples) or 1.0
    scale = 0.7 / peak
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(sample_rate)
        frames = b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, s * scale)) * 32767))
            for s in samples
        )
        w.writeframes(frames)


def _play_file(path: Path, player: str) -> None:
    """Invoke a system player on `path`. Suppresses all output."""
    cmd = [player]
    if player == "ffplay":
        cmd += ["-nodisp", "-autoexit", "-loglevel", "quiet", str(path)]
    elif player == "mpv":
        cmd += ["--no-video", "--really-quiet", str(path)]
    elif player == "mpg123":
        cmd += ["-q", str(path)]
    elif player == "aplay":
        cmd += ["-q", str(path)]
    else:  # paplay
        cmd += [str(path)]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except Exception:
        pass


def play(sound_path: str = "", volume: float = 0.7) -> None:
    """Play a notification sound in a background thread.

    If `sound_path` is empty, a default synthesised chime is used.
    `volume` is informational for now (0..1); system mixer controls actual level.
    """
    def _worker() -> None:
        player = _find_player()
        if player is None:
            return  # No audio backend available; silent fail.

        if sound_path and Path(sound_path).is_file():
            _play_file(Path(sound_path), player)
        else:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                _synth_default_chime(tmp_path)
                _play_file(tmp_path, player)
            finally:
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass

    threading.Thread(target=_worker, daemon=True).start()
