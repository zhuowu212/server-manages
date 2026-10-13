from __future__ import annotations

import os
import uuid
from pathlib import Path


def data_root() -> Path:
    return Path(os.environ.get("DATA_ROOT", "/data"))


def current_pointer() -> Path:
    return data_root() / "CURRENT"


def new_generation() -> Path:
    generation = data_root() / "generations" / str(uuid.uuid4())
    generation.mkdir(parents=True, exist_ok=False)
    return generation
