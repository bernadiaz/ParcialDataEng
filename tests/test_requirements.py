"""requirements.txt (pipeline container, pip install -r) and pyproject.toml (`make install` on the host)
must describe the same libraries: every dependency of pyproject.toml is pinned in requirements.txt, at a
version inside its range."""
from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def _pins() -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        requirement = Requirement(line)
        specifiers = list(requirement.specifier)
        assert len(specifiers) == 1 and specifiers[0].operator == "==", f"{line}: pin one exact version"
        pins[canonicalize_name(requirement.name)] = specifiers[0].version
    return pins


def test_requirements_pin_every_pyproject_dependency_inside_its_range():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    pins = _pins()
    for line in project["dependencies"] + project["optional-dependencies"]["dev"]:
        requirement = Requirement(line)
        name = canonicalize_name(requirement.name)
        assert name in pins, f"{requirement.name} is in pyproject.toml but not in requirements.txt"
        assert requirement.specifier.contains(pins[name], prereleases=True), \
            f"requirements.txt pins {requirement.name}=={pins[name]}, outside pyproject.toml's {requirement.specifier}"
