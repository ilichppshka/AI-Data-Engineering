"""Проверки к ЛР 1."""
from __future__ import annotations

import pandas as pd

from checks.common import check, lab_result, record
from paths import STAGING

REQUIRED = ["order_date", "n_orders", "n_items", "revenue", "freight"]


def _as_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.date


def check_task_1(daily, orders: pd.DataFrame, items: pd.DataFrame):
    """Проверяет витрину daily_orders по свойствам результата, а не по коду."""
    if daily is None or not isinstance(daily, pd.DataFrame) or daily.empty:
        record("lab01", "task_1", False, "витрина не построена")
        print("── Задание " + "─" * 55)
        print(" ✗ переменная `daily` пуста или не является DataFrame")
        print("     → соберите витрину и запустите ячейку проверки ещё раз\n")
        return None

    missing = [c for c in REQUIRED if c not in daily.columns]
    if missing:
        return check("lab01", "task_1", [
            (f"есть все нужные колонки {REQUIRED}", False,
             f"не хватает: {missing}")], title="Задание: таблица заказов по дням")

    ref = orders.copy()
    ref["order_date"] = _as_date(ref["order_purchase_timestamp"])
    ref_daily = ref.groupby("order_date").agg(n_orders=("order_id", "nunique"))

    got = daily.copy()
    got["order_date"] = _as_date(got["order_date"])
    got_daily = got.set_index("order_date").sort_index()

    same_days = set(ref_daily.index) == set(got_daily.index)
    merged = ref_daily.join(got_daily[["n_orders"]], how="outer",
                            lsuffix="_ref", rsuffix="_got")
    per_day_ok = bool(same_days) and bool(
        (merged["n_orders_ref"] == merged["n_orders_got"]).all())
    bad_days = 0 if per_day_ok else int(
        (merged["n_orders_ref"] != merged["n_orders_got"]).sum())

    tot_orders = int(pd.to_numeric(daily["n_orders"]).sum())
    tot_items = int(pd.to_numeric(daily["n_items"]).sum())
    rev = float(pd.to_numeric(daily["revenue"]).sum())
    fre = float(pd.to_numeric(daily["freight"]).sum())

    exp_orders = len(orders)
    exp_items = len(items)
    exp_rev = float(items["price"].sum())
    exp_fre = float(items["freight_value"].sum())

    no_nan = bool(daily[REQUIRED].notna().all().all())
    unique_days = bool(daily["order_date"].is_unique)
    int_like = (pd.api.types.is_integer_dtype(daily["n_orders"])
                and pd.api.types.is_integer_dtype(daily["n_items"]))

    rows = [
        ("одна строка на дату – зерно таблицы", unique_days,
         "одна и та же дата встречается несколько раз – свёртка выполнена не до конца"),
        ("в таблице те же дни, что и в orders", same_days,
         "часть дней потерялась или появились лишние: подумайте, какое соединение "
         "сохраняет заказы без позиций"),
        ("n_orders совпадает с orders по каждому дню", per_day_ok,
         f"расходится дней: {bad_days}. Скорее всего, после соединения с позициями "
         "заказы размножились – сверните правую таблицу до зерна заказа "
         "перед соединением"),
        (f"всего заказов = {exp_orders}", tot_orders == exp_orders,
         f"получилось {tot_orders}; разница {tot_orders - exp_orders} строк – признак "
         "размножения строк при соединении либо потерянных заказов"),
        (f"всего позиций = {exp_items}", tot_items == exp_items,
         f"получилось {tot_items}; проверьте, что считаете позиции, "
         "а не строки после соединения"),
        ("сумма revenue сходится с order_items", abs(rev - exp_rev) < 1.0,
         f"ожидалось {exp_rev:,.2f}, получено {rev:,.2f}"),
        ("сумма freight сходится с order_items", abs(fre - exp_fre) < 1.0,
         f"ожидалось {exp_fre:,.2f}, получено {fre:,.2f}"),
        ("нет пропусков в таблице", no_nan,
         "у заказов без позиций метрики должны быть 0, а не NaN – "
         "иначе потребитель витрины получит NaN в сумме"),
        ("n_orders и n_items – целые числа", int_like,
         "количество не бывает дробным; приведите тип явно"),
    ]
    return check("lab01", "task_1", rows, title="Задание: таблица заказов по дням")


def lab01_result() -> bool:
    return lab_result(
        "lab01",
        [("task_1", "таблица по дням построена и сходится с источником")],
        artifacts=[("data/staging/lab01_daily_orders.parquet",
                    STAGING / "lab01_daily_orders.parquet")],
    )
