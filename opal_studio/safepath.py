"""
Opal - Safe path building
Plain English: One place where a file path is put together. Every path that
Opal writes to is built here, and the result is checked to make sure it stays
inside the folder it is supposed to be in.

The app reads names out of archives, out of documents and out of the file
system, so a name like "../../something" has to be refused rather than
followed. This module is that refusal, in one place.
"""

from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


class UnsafePathError(ValueError):
    """Raised when a path would leave the folder it is supposed to stay in."""


def safe_path(base: PathLike, *parts: str) -> Path:
    """Joins a name onto a folder and refuses to leave it.

    Absolute names, drive letters and any ".." are removed, and the result
    must still sit inside the base folder. Raises UnsafePathError otherwise.
    """
    base_path = Path(base)
    cleaned: list[str] = []
    for part in parts:
        if part is None:
            continue
        text = str(part).replace("\\", "/")
        # A Windows drive letter or a UNC path is not a name we want to keep.
        if len(text) > 1 and text[1] == ":":
            text = text[2:]
        for piece in text.split("/"):
            if piece in ("", "."):
                continue
            if piece == "..":
                # Never step upwards, however the name was written.
                if cleaned:
                    cleaned.pop()
                continue
            cleaned.append(piece)
    if not cleaned:
        raise UnsafePathError("Refusing an empty path")
    target = base_path.joinpath(*cleaned)
    try:
        target.resolve().relative_to(base_path.resolve())
    except ValueError:
        raise UnsafePathError(
            f"Refusing to write outside the folder: {parts!r}")
    return target


def safe_output_path(base: PathLike, name: str, suffix: str = "") -> Path:
    """The path for a result file, kept beside the file it came from."""
    stem = Path(name).stem
    tail = Path(name).suffix
    file_name = f"{stem}{suffix}{tail}"
    return safe_path(base, file_name)
