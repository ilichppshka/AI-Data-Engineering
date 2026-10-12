#!/usr/bin/env python3
"""Сводка по всем работам курса.

    python course_check.py
    python course_check.py --verbose

Показывает, какие задания зачтены и какие файлы созданы.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import paths                                               # noqa: E402
from checks.common import load_results                     # noqa: E402

LABS = {
    "lab01": {
        "title": "ЛР 1. Как движутся данные",
        "items": [("task_1", "витрина daily_orders")],
        "artifacts": [paths.STAGING / "lab01_daily_orders.parquet"],
    },
    "lab02": {
        "title": "ЛР 2. Форматы хранения и SQL",
        "items": [("task_1", "orders_enriched"), ("task_2", "monthly_revenue")],
        "artifacts": [paths.WAREHOUSE,
                      paths.STAGING / "lab02_orders_enriched.parquet"],
    },
    "lab03": {
        "title": "ЛР 3. ETL и качество данных",
        "items": [("task_1", "clean_orders + карантин"),
                  ("task_2", "clean_payments"),
                  ("task_3", "clean_reviews")],
        "artifacts": [paths.CLEAN / "clean_orders.parquet",
                      paths.CLEAN / "clean_payments.parquet",
                      paths.CLEAN / "clean_reviews.parquet",
                      paths.CLEAN / "clean_items.parquet",
                      paths.QUALITY / "lab03_report.json"],
    },
    "lab04": {
        "title": "ЛР 4. DWH и витрины",
        "items": [("task_1", "fact_order_items"),
                  ("task_2", "mart_category_month"),
                  ("task_3", "mart_seller_delivery")],
        "artifacts": [paths.MARTS / "mart_category_month.parquet",
                      paths.MARTS / "mart_seller_delivery.parquet"],
    },
    "lab05": {
        "title": "ЛР 5. Pipeline и идемпотентность",
        "items": [("task_2", "DAG собран"),
                  ("task_1", "идемпотентность build_mart"),
                  ("task_3", "backfill")],
        "artifacts": [paths.RUNS / "olist_daily_latest.json",
                      paths.LOGS / "olist_daily.log"],
    },
    "lab06": {
        "title": "ЛР 6. Масштаб, стриминг, ML",
        "items": [("task_1", "партиционирование"),
                  ("task_2", "идемпотентный consumer"),
                  ("task_3", "признаки без утечки")],
        "artifacts": [paths.MARTS / "fact_partitioned",
                      paths.MARTS / "features_orders.parquet",
                      paths.MARTS / "model_metrics.parquet"],
    },
}


def check_lab(lab: str, spec: dict, verbose: bool = False) -> tuple[int, int]:
    data = load_results(lab)
    done = total = 0
    lines = []
    for key, desc in spec["items"]:
        total += 1
        st = data.get(key)
        if st is None:
            lines.append(f"    ✗ {desc}: проверка не запускалась")
        elif st["passed"]:
            done += 1
            lines.append(f"    ✓ {desc}")
        else:
            lines.append(f"    ✗ {desc}: {st.get('detail', '')[:80]}")
    missing = [a for a in spec["artifacts"] if not Path(a).exists()]
    status = "✓" if (done == total and not missing) else (
        "~" if done else "✗")
    print(f" {status} {spec['title']:<38} {done}/{total} проверок"
          + (f", нет артефактов: {len(missing)}" if missing else ""))
    if verbose or missing or done != total:
        for line in lines:
            print(line)
        for a in missing:
            print(f"    ✗ нет артефакта: {Path(a).relative_to(ROOT)}")
    return done, total


def data_quality_summary() -> None:
    p = paths.QUALITY / "lab03_report.json"
    if not p.exists():
        return
    rep = json.loads(p.read_text(encoding="utf-8"))
    verdict = ("все проверки пройдены" if rep["all_passed"]
               else ("критических нарушений нет, есть предупреждения"
                     if rep["n_critical_failures"] == 0
                     else "ЕСТЬ КРИТИЧЕСКИЕ НАРУШЕНИЯ"))
    print(f"\n Отчёт о качестве данных (ЛР 3): {verdict} "
          f"(критических: {rep['n_critical_failures']})")
    for t in rep["tables"]:
        bad = [e["name"] for e in t["expectations"] if not e["passed"]]
        mark = "✓" if not bad else "!"
        print(f"   {mark} {t['table']:<18} {t['n_rows']:>8,} строк"
              + (f"   нарушено: {', '.join(bad)[:60]}" if bad else ""))


def main() -> int:
    verbose = "--verbose" in sys.argv
    print("=" * 72)
    print("ПРОВЕРКА КУРСА «Технологии инженерии данных в области ИИ»".center(72))
    print("=" * 72)
    src = (paths.RAW_OLIST / "_SOURCE.txt")
    print(f" данные: {src.read_text(encoding='utf-8').strip() if src.exists() else 'НЕ ЗАГРУЖЕНЫ'}")
    print("-" * 72)
    done = total = 0
    for lab, spec in LABS.items():
        d, t = check_lab(lab, spec, verbose)
        done += d
        total += t
    data_quality_summary()
    print("-" * 72)
    print(f" ИТОГО: {done}/{total} проверок пройдено")
    if done == total:
        print(" Курс пройден полностью ✅")
    elif done >= total * 0.6:
        print(" Курс пройден частично ⚠️")
    else:
        print(" Большая часть работы не выполнена ❌")
    print("=" * 72)
    return 0 if done == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
