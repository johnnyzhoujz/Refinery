"""File loading utilities for prompts and evals."""

import glob
from pathlib import Path
from typing import Dict


def load_files_from_path(path_pattern: str) -> Dict[str, str]:
    """
    Load files matching glob pattern into {filename: content} dict.

    Args:
        path_pattern: Path or glob pattern (e.g., './prompts/*.txt', './prompts/')

    Returns:
        Dictionary mapping filename to file content
    """
    files = {}

    # If path_pattern is a directory, load all files in it
    path = Path(path_pattern)
    if path.is_dir():
        matched_paths = list(path.rglob("*"))
    else:
        # Use glob for pattern matching
        matched_paths = [Path(p) for p in glob.glob(path_pattern, recursive=True)]

    for file_path in matched_paths:
        if file_path.is_file():
            try:
                content = file_path.read_text()
                files[file_path.name] = content
            except Exception as e:
                # Skip files that can't be read (binary, permissions, etc.)
                continue

    return files
