from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional

from dotenv import load_dotenv

_DEFAULT_ENV_FILES = (".env",)


def find_env_file(start: Path, names: Iterable[str] = _DEFAULT_ENV_FILES) -> Optional[Path]:
    root = start if start.is_dir() else start.parent
    for name in names:
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def load_env(
    env_override_var: Optional[str],
    start: Optional[Path] = None,
    names: Iterable[str] = _DEFAULT_ENV_FILES,
) -> Optional[Path]:
    override = os.environ.get(env_override_var) if env_override_var else None
    if override:
        env_path = Path(override)
        load_dotenv(dotenv_path=env_path, override=False)
        return env_path

    search_start = start or Path.cwd()
    env_path = find_env_file(search_start, names=names)
    if env_path:
        load_dotenv(dotenv_path=env_path, override=False)
    return env_path


def is_env_enabled(env_names: Iterable[str]) -> bool:
    enabled_values = {"1", "true", "yes", "on"}
    for name in env_names:
        value = os.environ.get(name)
        if value is not None and value.strip().lower() in enabled_values:
            return True
    return False


def log_env_loaded(env_path: Optional[Path], source: str, trace_enabled: bool) -> None:
    if not trace_enabled:
        return
    if env_path:
        print(f"[trace] env loaded ({source}): {env_path}")
    else:
        print(f"[trace] env loaded ({source}): <none>")
