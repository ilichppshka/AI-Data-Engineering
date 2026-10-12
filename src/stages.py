"""Подготовка слоёв данных, на которые опирается работа.

Слой parquet – это перекладывание исходных CSV, его восстанавливаем молча.
Слои clean и core студент строит сам, поэтому здесь мы только проверяем,
что они есть, и объясняем, чего не хватает.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

import paths
from get_data import get_olist, source_kind
from notebook_env import data_mode, describe_data_source


TABLES = ("orders", "order_items", "order_payments", "order_reviews",
          "customers", "products", "sellers")


def _raw_name(name: str) -> str:
    return f"olist_{name}_dataset.csv"


def ensure_parquet() -> Path:
    target = paths.PARQUET / "olist_orders_dataset.parquet"
    if target.exists():
        return paths.PARQUET
    raw = get_olist(prefer=data_mode())
    describe_data_source(source_kind())
    print("↻ Восстанавливаю RAW/Parquet из исходных CSV (результат ЛР 2)…")
    # ЛР 6 также сравнивает CSV и Parquet для geolocation, поэтому
    # восстанавливаем весь RAW, а не только семь таблиц CLEAN.
    for csv_path in raw.glob("*.csv"):
        pd.read_csv(csv_path).to_parquet(
            paths.PARQUET / csv_path.name.replace(".csv", ".parquet"), index=False)
    return paths.PARQUET


def ensure_stage(stage: str) -> Path:
    """Готовит слой данных, если его ещё нет.

    parquet восстанавливается всегда: это просто перекладывание исходных CSV.
    clean и core студент строит сам в третьей и четвёртой работах, поэтому без
    них тетрадь не продолжает работу, а объясняет, чего не хватает.
    """
    if stage == "parquet":
        return ensure_parquet()
    if stage not in ("clean", "core"):
        raise ValueError(f"неизвестный слой: {stage}")

    ready = {"clean": paths.CLEAN / "clean_orders.parquet",
             "core": paths.WAREHOUSE}[stage]
    if ready.exists():
        return ready.parent

    try:
        import _restore
    except ImportError:
        work = {"clean": "третьей", "core": "четвёртой"}[stage]
        raise FileNotFoundError(
            f"Нет данных слоя {stage.upper()}: он создаётся в {work} работе.\n"
            f"Выполните её и запустите эту тетрадь снова."
        ) from None
    return _restore.ensure_clean() if stage == "clean" else _restore.ensure_core()
