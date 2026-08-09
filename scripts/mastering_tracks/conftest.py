"""
Shared pytest fixtures for the master_tracks.py test suite.

Since `matchering` does real audio DSP and needs actual audio files, the
tests never call the real library. Instead a lightweight fake module is
injected into sys.modules before master_tracks.py is imported, so the
script's `mg.process` / `mg.pcm16` / `mg.pcm24` / `mg.log` calls are
captured and verifiable without any audio processing or the real
dependency being installed.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

# Make the script importable (tests/ sits next to master_tracks.py)
SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


class _FakeResult:
    """Stand-in for matchering's mg.pcm16()/mg.pcm24() result objects."""

    def __init__(self, path: str, bit_depth: int):
        self.path = path
        self.bit_depth = bit_depth

    def __repr__(self):
        return f"<FakeResult {self.path!r} {self.bit_depth}bit>"


class FakeMatchering(types.ModuleType):
    """A minimal stand-in for the real `matchering` package."""

    def __init__(self):
        super().__init__("matchering")
        self.process_calls: list[dict] = []
        self.logged: list = []

    def process(self, target, reference, results):
        self.process_calls.append(
            {"target": target, "reference": reference, "results": results}
        )
        # Simulate the real library's side effect: writing output file(s).
        for result in results:
            out_path = Path(result.path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(b"FAKE-MASTERED-AUDIO")

    def pcm16(self, path):
        return _FakeResult(path, 16)

    def pcm24(self, path):
        return _FakeResult(path, 24)

    def log(self, fn):
        self.logged.append(fn)


@pytest.fixture
def fake_mg(monkeypatch):
    """Install a fresh FakeMatchering instance as the `matchering` module."""
    fake = FakeMatchering()
    monkeypatch.setitem(sys.modules, "matchering", fake)
    return fake


@pytest.fixture
def mt(fake_mg):
    """
    Import master_tracks freshly for each test, bound to the fake
    matchering module (module-level BIT_DEPTH_SAVERS is built at import
    time, so a stale cached import would reference a stale fake).
    """
    sys.modules.pop("master_tracks", None)
    import master_tracks  # noqa: F401  (imported for its side effects/binding)

    return master_tracks


@pytest.fixture
def audio_file(tmp_path):
    """Factory fixture: create a small dummy 'audio' file and return its Path."""

    def _make(name: str = "track.wav", data: bytes = b"RIFF-FAKE-AUDIO") -> Path:
        path = tmp_path / name
        path.write_bytes(data)
        return path

    return _make
