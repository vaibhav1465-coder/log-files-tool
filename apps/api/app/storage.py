import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from .config import get_settings


@dataclass(frozen=True)
class StoredFile:
    path: Path
    size_bytes: int
    sha256: str


async def store_upload(run_id: UUID, file_id: UUID, upload: UploadFile) -> StoredFile:
    root = Path(get_settings().storage_root)
    target_dir = root / str(run_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload.filename or "source.log").suffix.lower()
    target = target_dir / f"{file_id}{suffix}"
    digest = hashlib.sha256()
    size = 0
    with target.open("xb") as output:
        while chunk := await upload.read(8 * 1024 * 1024):
            output.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    return StoredFile(path=target, size_bytes=size, sha256=digest.hexdigest())


def ensure_capacity(expected_size: int) -> None:
    settings = get_settings()
    if expected_size <= 0 or expected_size > settings.max_file_bytes:
        raise OSError(f"File size must be between 1 and {settings.max_file_bytes} bytes")
    root = Path(settings.storage_root)
    root.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(root).free
    required = expected_size + settings.storage_reserve_bytes
    if free < required:
        raise OSError(f"Insufficient storage: {free} bytes free; {required} required")


def upload_target(run_id: UUID, file_id: UUID, filename: str) -> Path:
    root = Path(get_settings().storage_root)
    target_dir = root / str(run_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix.lower()
    return target_dir / f"{file_id}{suffix}.uploading"


def append_chunk(target: Path, offset: int, content: bytes) -> int:
    current = target.stat().st_size if target.exists() else 0
    if current != offset:
        raise ValueError(f"Upload offset mismatch: expected {current}, received {offset}")
    with target.open("ab", buffering=0) as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())
    return current + len(content)


def finalize_upload(target: Path, expected_size: int) -> StoredFile:
    actual_size = target.stat().st_size
    if actual_size != expected_size:
        raise ValueError(f"Incomplete upload: expected {expected_size}, received {actual_size}")
    digest = hashlib.sha256()
    with target.open("rb") as source:
        while chunk := source.read(16 * 1024 * 1024):
            digest.update(chunk)
    final_path = target.with_suffix("")
    target.replace(final_path)
    return StoredFile(path=final_path, size_bytes=actual_size, sha256=digest.hexdigest())
