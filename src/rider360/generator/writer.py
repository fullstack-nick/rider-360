from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from rider360.generator.schemas import SCHEMAS

ROW_GROUP_SIZE = 100_000


class DatasetWriter:
    """Stream deterministic Arrow batches into one Parquet file per source table."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._writers: dict[str, pq.ParquetWriter] = {}
        self._pending: dict[str, list[pa.Table]] = defaultdict(list)
        self._pending_counts: dict[str, int] = defaultdict(int)
        self.counts: dict[str, int] = defaultdict(int)

    def write(self, table_name: str, records: Iterable[Mapping[str, Any]]) -> None:
        rows = list(records)
        if not rows:
            return
        schema = SCHEMAS[table_name]
        table = pa.Table.from_pylist(rows, schema=schema)
        self._pending[table_name].append(table)
        self._pending_counts[table_name] += len(rows)
        self.counts[table_name] += len(rows)
        if self._pending_counts[table_name] >= ROW_GROUP_SIZE:
            self._flush(table_name)

    def _writer_for(self, table_name: str) -> pq.ParquetWriter:
        writer = self._writers.get(table_name)
        if writer is not None:
            return writer
        directory = self.output_dir / table_name
        directory.mkdir(parents=True, exist_ok=True)
        writer = pq.ParquetWriter(
            directory / "part-00000.parquet",
            SCHEMAS[table_name],
            compression="zstd",
            compression_level=8,
            use_dictionary=True,
            write_statistics=True,
        )
        self._writers[table_name] = writer
        return writer

    def _flush(self, table_name: str, *, force: bool = False) -> None:
        pending = self._pending[table_name]
        if not pending:
            return
        combined = pending[0] if len(pending) == 1 else pa.concat_tables(pending)
        emit_rows = (
            combined.num_rows if force else (combined.num_rows // ROW_GROUP_SIZE) * ROW_GROUP_SIZE
        )
        if emit_rows == 0:
            return
        self._writer_for(table_name).write_table(
            combined.slice(0, emit_rows), row_group_size=ROW_GROUP_SIZE
        )
        remaining = combined.slice(emit_rows)
        self._pending[table_name] = [remaining] if remaining.num_rows else []
        self._pending_counts[table_name] = remaining.num_rows

    def close(self) -> None:
        for table_name in list(self._pending):
            self._flush(table_name, force=True)
        for writer in self._writers.values():
            writer.close()
        self._writers.clear()
        self._pending.clear()
        self._pending_counts.clear()

    def manifest(self, metadata: Mapping[str, Any]) -> dict[str, Any]:
        files: dict[str, dict[str, Any]] = {}
        for table_name in sorted(self.counts):
            path = self.output_dir / table_name / "part-00000.parquet"
            with path.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            files[table_name] = {
                "path": str(path.relative_to(self.output_dir)).replace("\\", "/"),
                "row_count": self.counts[table_name],
                "sha256": digest,
                "size_bytes": path.stat().st_size,
            }
        return {**metadata, "tables": files}


def write_manifest(output_dir: Path, manifest: Mapping[str, Any]) -> Path:
    path = output_dir / "manifest.json"
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return path
