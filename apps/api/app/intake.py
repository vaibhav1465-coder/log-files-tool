import io
from pathlib import PurePosixPath
from typing import BinaryIO, Iterator
from zipfile import BadZipFile, ZipFile


MAX_FILES_PER_BATCH = 1
MAX_ARCHIVE_ENTRIES = 100
MAX_PREFLIGHT_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
SAMPLE_LINES = 10_000


class IntakeFailure(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _safe_entry_name(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    return not path.is_absolute() and ".." not in path.parts


def _decoded_lines(stream: BinaryIO) -> Iterator[str]:
    wrapper = io.TextIOWrapper(stream, encoding="utf-8", errors="replace", newline="")
    try:
        yield from wrapper
    finally:
        wrapper.detach()


def iter_preflight_lines(file: BinaryIO, filename: str) -> tuple[Iterator[str], int]:
    lower = filename.lower()
    if not lower.endswith(".zip"):
        return _decoded_lines(file), 1

    try:
        archive = ZipFile(file)
    except BadZipFile as exc:
        raise IntakeFailure("ARCHIVE_INVALID", "The ZIP file is corrupt or unsupported.") from exc

    entries = [entry for entry in archive.infolist() if not entry.is_dir()]
    if not entries:
        archive.close()
        raise IntakeFailure("ARCHIVE_EMPTY", "The ZIP file contains no log entries.")
    if len(entries) > MAX_ARCHIVE_ENTRIES:
        archive.close()
        raise IntakeFailure("ARCHIVE_TOO_MANY_ENTRIES", f"Archive contains more than {MAX_ARCHIVE_ENTRIES} files.")

    for entry in entries:
        if not _safe_entry_name(entry.filename):
            archive.close()
            raise IntakeFailure("ARCHIVE_PATH_REJECTED", "Archive contains an unsafe file path.")
        if entry.flag_bits & 0x1:
            archive.close()
            raise IntakeFailure("ARCHIVE_ENCRYPTED", "Encrypted ZIP entries are not supported.")
        if entry.filename.lower().endswith((".zip", ".gz", ".gzip")):
            archive.close()
            raise IntakeFailure("ARCHIVE_NESTED", "Nested archives are not supported.")
        ratio = entry.file_size / max(entry.compress_size, 1)
        if ratio > MAX_COMPRESSION_RATIO:
            archive.close()
            raise IntakeFailure("ARCHIVE_RATIO_REJECTED", "Archive compression ratio exceeds the safety limit.")

    def generate() -> Iterator[str]:
        consumed = 0
        try:
            for entry in entries:
                if consumed >= MAX_PREFLIGHT_UNCOMPRESSED_BYTES:
                    break
                with archive.open(entry) as stream:
                    for line in _decoded_lines(stream):
                        consumed += len(line.encode("utf-8", errors="replace"))
                        if consumed > MAX_PREFLIGHT_UNCOMPRESSED_BYTES:
                            return
                        yield line
        finally:
            archive.close()

    return generate(), len(entries)


def iter_analysis_lines(file: BinaryIO, filename: str) -> tuple[Iterator[str], int]:
    lower = filename.lower()
    if not lower.endswith(".zip"):
        return _decoded_lines(file), 1

    try:
        archive = ZipFile(file)
    except BadZipFile as exc:
        raise IntakeFailure("ARCHIVE_INVALID", "The ZIP file is corrupt or unsupported.") from exc
    entries = [entry for entry in archive.infolist() if not entry.is_dir()]
    if not entries or len(entries) > MAX_ARCHIVE_ENTRIES:
        archive.close()
        raise IntakeFailure("ARCHIVE_ENTRY_REJECTED", "Archive entry count is outside the supported range.")
    for entry in entries:
        if not _safe_entry_name(entry.filename) or entry.flag_bits & 0x1:
            archive.close()
            raise IntakeFailure("ARCHIVE_ENTRY_REJECTED", "Archive contains an unsafe or encrypted entry.")
        if entry.filename.lower().endswith((".zip", ".gz", ".gzip")):
            archive.close()
            raise IntakeFailure("ARCHIVE_NESTED", "Nested archives are not supported.")
        if entry.file_size / max(entry.compress_size, 1) > MAX_COMPRESSION_RATIO:
            archive.close()
            raise IntakeFailure("ARCHIVE_RATIO_REJECTED", "Archive compression ratio exceeds the safety limit.")

    def generate() -> Iterator[str]:
        try:
            for entry in entries:
                with archive.open(entry) as stream:
                    yield from _decoded_lines(stream)
        finally:
            archive.close()

    return generate(), len(entries)
