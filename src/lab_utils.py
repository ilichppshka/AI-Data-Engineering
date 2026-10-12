"""Мелкие утилиты, общие для лабораторных."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def require_artifact(path: str | Path, produced_by: str) -> Path:
    """Явная зависимость между лабораторными: артефакт должен существовать."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Не найден артефакт {p}.\n"
            f"Он создаётся в {produced_by}. Выполните её полностью "
            f"и запустите этот ноутбук ещё раз."
        )
    return p


def read_parquet_dir(folder: str | Path, names: list[str]) -> dict[str, pd.DataFrame]:
    folder = Path(folder)
    return {n: pd.read_parquet(folder / f"{n}.parquet") for n in names}


def save_table(df: pd.DataFrame, folder: str | Path, name: str) -> Path:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.parquet"
    df.to_parquet(path, index=False)      # перезапись => шаг идемпотентен
    return path
