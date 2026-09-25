from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from app.core.config import settings


def to_posix_path(path: Path | str) -> str:
    """Normalize any path (including Windows paths) to POSIX forward slashes."""
    return str(path).replace("\\", "/")


def resolve_media_path(raw_path: Optional[str], default_dir: Optional[str] = None) -> Optional[Path]:
    """
    Cross-platform media path resolver.
    Handles Windows vs Linux separators, relative vs absolute paths, and folder relocations.
    Returns the resolved existing Path, or None if the file does not exist on disk.
    """
    if not raw_path:
        return None

    # 1. Normalize separators
    normalized = raw_path.replace("\\", "/").strip()
    p = Path(normalized)

    # 2. Check direct path
    if p.exists() and p.is_file():
        return p.resolve()

    # 3. Check relative to current working directory and repo root
    cwd = Path.cwd()
    backend_dir = Path(__file__).resolve().parent.parent.parent
    repo_root = backend_dir.parent

    candidates = [
        cwd / normalized.lstrip("./").lstrip("/"),
        backend_dir / normalized.lstrip("./").lstrip("/"),
        repo_root / normalized.lstrip("./").lstrip("/"),
    ]

    for cand in candidates:
        if cand.exists() and cand.is_file():
            return cand.resolve()

    # 4. Check by filename inside default_dir (e.g., settings.UPLOAD_DIR or PROCESSED_DIR)
    filename = p.name
    if filename and default_dir:
        dir_norm = default_dir.replace("\\", "/").strip()
        dir_candidates = [
            Path(dir_norm) / filename,
            cwd / dir_norm.lstrip("./").lstrip("/") / filename,
            backend_dir / dir_norm.lstrip("./").lstrip("/") / filename,
        ]
        for dc in dir_candidates:
            if dc.exists() and dc.is_file():
                return dc.resolve()

    return None
