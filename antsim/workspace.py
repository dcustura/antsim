"""Locations and model-file loading shared by every command."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from .model import Model

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
MODELS = ROOT / "models"


def out_root() -> Path:
    """Where results go: $ANTSIM_OUT, else <repo>/out."""
    return Path(os.environ.get("ANTSIM_OUT", ROOT / "out"))


def load_module(path: Path):
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"model file not found: {path}")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_models(path: Path) -> list[Model]:
    """A model file defines `model = Model(...)` or `models = [...]`."""
    mod = load_module(path)
    if hasattr(mod, "models"):
        return list(mod.models)
    if hasattr(mod, "model"):
        return [mod.model]
    raise SystemExit(f"{path}: define `model = Model(...)` or `models = [...]`")


def load_build(path: Path):
    """A tunable model file defines `build(length) -> Model`."""
    mod = load_module(path)
    if not hasattr(mod, "build"):
        raise SystemExit(f"{path}: define `build(length) -> Model` to use tune/multiband")
    return mod.build
