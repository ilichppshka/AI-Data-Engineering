"""Пути проекта.

Тетради лежат в notebooks и solutions, данные – в data. Чтобы один и тот же
код работал из любой папки, корень ищем вверх по дереву по файлу .course-root.
"""
from __future__ import annotations

from pathlib import Path


def project_root(start: Path | None = None) -> Path:
    p = (start or Path.cwd()).resolve()
    for cand in [p, *p.parents]:
        if (cand / ".course-root").exists():
            return cand
    raise RuntimeError(
        "Не найден корень проекта (.course-root). "
        "Запускайте ноутбуки внутри папки курса."
    )


ROOT = project_root()
SRC = ROOT / "src"
DATA = ROOT / "data"
RAW = DATA / "raw"
RAW_OLIST = RAW / "olist"
STAGING = DATA / "staging"
PARQUET = STAGING / "parquet"
CLEAN = STAGING / "clean"
PROCESSED = DATA / "processed"
MARTS = DATA / "marts"
QUALITY = DATA / "quality"
RUNS = DATA / "_runs"
LOGS = ROOT / "logs"
WAREHOUSE = PROCESSED / "warehouse.duckdb"


def ensure_dirs() -> None:
    for d in (RAW, RAW_OLIST, STAGING, PARQUET, CLEAN, PROCESSED, MARTS,
              QUALITY, RUNS, LOGS):
        d.mkdir(parents=True, exist_ok=True)

