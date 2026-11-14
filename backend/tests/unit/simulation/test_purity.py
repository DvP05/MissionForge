"""The simulation package is pure: no wall clock, env, network or unseeded randomness."""

import re
from pathlib import Path

import app.domain.simulation as sim_pkg

SIM_DIR = Path(sim_pkg.__file__).resolve().parent
FORBIDDEN = re.compile(
    r"\btime\.|datetime\.now|\bos\.environ|\bgetenv\b"
    r"|\bimport (time|socket|urllib|httpx|requests)\b"
)


def _sources() -> list[Path]:
    files = sorted(SIM_DIR.glob("*.py"))
    assert files, "simulation package has no modules"
    return files


def test_no_time_env_or_network_in_simulation() -> None:
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        assert not FORBIDDEN.search(text), f"{path.name} uses a forbidden API"


def test_only_prng_module_touches_random() -> None:
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        if path.name != "prng.py":
            assert "import random" not in text and "random.Random(" not in text, path.name
