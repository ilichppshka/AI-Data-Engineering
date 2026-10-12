"""Проверки к ЛР 2."""
from __future__ import annotations

import re

from checks.common import check, lab_result, record
from paths import STAGING, WAREHOUSE

T1_COLS = ["order_id", "customer_id", "order_status", "order_date",
           "payment_total", "payment_count", "n_items", "items_total",
           "freight_total"]
T2_COLS = ["month", "n_orders", "revenue", "revenue_cumulative", "revenue_prev"]


def _table_exists(con, name: str) -> bool:
    return bool(con.execute(
        "SELECT COUNT(*) FROM duckdb_tables() WHERE table_name = ?",
        [name]).fetchone()[0])


def _cols(con, name: str) -> list[str]:
    return [r[0] for r in con.execute(f"DESCRIBE {name}").fetchall()]


def _one(con, sql: str):
    return con.execute(sql).fetchone()[0]


def check_task_1(con):
    lab, item = "lab02", "task_1"
    if not _table_exists(con, "orders_enriched"):
        record(lab, item, False, "таблица orders_enriched не создана")
        print("── Задание 1 " + "─" * 54)
        print(" ✗ таблица orders_enriched не создана\n")
        return None

    cols = _cols(con, "orders_enriched")
    missing = [c for c in T1_COLS if c not in cols]
    if missing:
        return check(lab, item, [("есть все требуемые колонки", False,
                                  f"не хватает: {missing}")],
                     title="Задание 1: orders_enriched")

    n_orders_raw = _one(con, "SELECT COUNT(*) FROM raw_orders")
    n_rows = _one(con, "SELECT COUNT(*) FROM orders_enriched")
    n_uniq = _one(con, "SELECT COUNT(DISTINCT order_id) FROM orders_enriched")

    pay_sum_raw = float(_one(con, "SELECT SUM(payment_value) FROM raw_payments"))
    pay_cnt_raw = int(_one(con, "SELECT COUNT(*) FROM raw_payments"))
    itm_sum_raw = float(_one(con, "SELECT SUM(price) FROM raw_items"))
    fre_sum_raw = float(_one(con, "SELECT SUM(freight_value) FROM raw_items"))
    itm_cnt_raw = int(_one(con, "SELECT COUNT(*) FROM raw_items"))

    pay_sum = float(_one(con, "SELECT SUM(payment_total) FROM orders_enriched") or 0)
    pay_cnt = int(_one(con, "SELECT SUM(payment_count) FROM orders_enriched") or 0)
    itm_sum = float(_one(con, "SELECT SUM(items_total) FROM orders_enriched") or 0)
    fre_sum = float(_one(con, "SELECT SUM(freight_total) FROM orders_enriched") or 0)
    itm_cnt = int(_one(con, "SELECT SUM(n_items) FROM orders_enriched") or 0)

    nulls = int(_one(con, """
        SELECT COUNT(*) FROM orders_enriched
        WHERE payment_total IS NULL OR payment_count IS NULL
           OR n_items IS NULL OR items_total IS NULL OR freight_total IS NULL
           OR order_id IS NULL OR order_date IS NULL
    """))
    date_type = _one(con, """
        SELECT data_type FROM duckdb_columns()
        WHERE table_name = 'orders_enriched' AND column_name = 'order_date'
    """)

    def ratio(a, b):
        return f"(в {a / b:.2f} раза больше)" if b and a > b else ""

    rows = [
        (f"строк ровно столько же, сколько заказов ({n_orders_raw:,})",
         n_rows == n_orders_raw,
         f"получилось {n_rows:,}. Больше – значит соединение размножило заказы; "
         f"меньше – значит часть заказов потерялась при INNER JOIN"),
        ("order_id уникален – одна строка на заказ", n_uniq == n_rows,
         f"уникальных order_id {n_uniq:,} при {n_rows:,} строках"),
        ("сумма payment_total = сумме payment_value в raw_payments",
         abs(pay_sum - pay_sum_raw) < 1.0,
         f"ожидалось {pay_sum_raw:,.2f}, получено {pay_sum:,.2f} "
         f"{ratio(pay_sum, pay_sum_raw)} – платежи задвоились позициями заказа"),
        ("сумма payment_count = числу строк в raw_payments",
         pay_cnt == pay_cnt_raw,
         f"ожидалось {pay_cnt_raw:,}, получено {pay_cnt:,}"),
        ("сумма items_total = сумме price в raw_items",
         abs(itm_sum - itm_sum_raw) < 1.0,
         f"ожидалось {itm_sum_raw:,.2f}, получено {itm_sum:,.2f} "
         f"{ratio(itm_sum, itm_sum_raw)} – позиции задвоились платежами"),
        ("сумма freight_total = сумме freight_value в raw_items",
         abs(fre_sum - fre_sum_raw) < 1.0,
         f"ожидалось {fre_sum_raw:,.2f}, получено {fre_sum:,.2f}"),
        ("сумма n_items = числу строк в raw_items", itm_cnt == itm_cnt_raw,
         f"ожидалось {itm_cnt_raw:,}, получено {itm_cnt:,}"),
        ("нет NULL в ключевых и числовых колонках", nulls == 0,
         f"строк с NULL: {nulls:,}. У заказов без платежей/позиций должны быть нули"),
        ("order_date имеет тип DATE", str(date_type).upper().startswith("DATE"),
         f"тип колонки: {date_type}. Приведите тип явно"),
    ]
    return check(lab, item, rows, title="Задание 1: orders_enriched")


def _uses_window_function(sql: str | None) -> bool:
    """Проверяет, что ответ написан именно с SQL-window, а не постфактум."""
    if not isinstance(sql, str):
        return False
    without_comments = re.sub(r"--[^\n]*(?:\n|$)|/\*.*?\*/", "", sql,
                             flags=re.MULTILINE | re.DOTALL)
    return bool(re.search(r"\bover\s*\(", without_comments, flags=re.IGNORECASE))


def check_task_2(con, sql: str | None = None):
    lab, item = "lab02", "task_2"
    if not _table_exists(con, "monthly_revenue"):
        record(lab, item, False, "таблица monthly_revenue не создана")
        print("── Задание 2 " + "─" * 54)
        print(" ✗ таблица monthly_revenue не создана\n")
        return None

    cols = _cols(con, "monthly_revenue")
    missing = [c for c in T2_COLS if c not in cols]
    if missing:
        return check(lab, item, [("есть все требуемые колонки", False,
                                  f"не хватает: {missing}")],
                     title="Задание 2: monthly_revenue")

    n_rows = _one(con, "SELECT COUNT(*) FROM monthly_revenue")
    n_uniq = _one(con, "SELECT COUNT(DISTINCT month) FROM monthly_revenue")
    expected_months = _one(con, """
        SELECT COUNT(DISTINCT date_trunc('month', order_date)) FROM orders_enriched
    """) if _table_exists(con, "orders_enriched") else n_rows

    total_rev = float(_one(con, "SELECT SUM(revenue) FROM monthly_revenue") or 0)
    last_cum = float(_one(con, """
        SELECT revenue_cumulative FROM monthly_revenue ORDER BY month DESC LIMIT 1
    """) or 0)
    src_rev = float(_one(con, "SELECT SUM(items_total) FROM orders_enriched") or 0)
    orders_sum = int(_one(con, "SELECT SUM(n_orders) FROM monthly_revenue") or 0)
    orders_src = int(_one(con, "SELECT COUNT(*) FROM orders_enriched") or 0)

    bad_cum = int(_one(con, """
        WITH ref AS (
            SELECT month, revenue, revenue_cumulative,
                   SUM(revenue) OVER (ORDER BY month ROWS UNBOUNDED PRECEDING) AS expected
            FROM monthly_revenue
        )
        SELECT COUNT(*) FROM ref WHERE abs(revenue_cumulative - expected) > 0.5
    """))
    bad_lag = int(_one(con, """
        WITH ref AS (
            SELECT month, revenue_prev,
                   LAG(revenue) OVER (ORDER BY month) AS expected
            FROM monthly_revenue
        )
        SELECT COUNT(*) FROM ref
        WHERE (revenue_prev IS NULL) <> (expected IS NULL)
           OR abs(COALESCE(revenue_prev, 0) - COALESCE(expected, 0)) > 0.5
    """))

    rows = [
        ("одна строка на месяц", n_rows == n_uniq and n_rows > 0,
         f"строк {n_rows}, уникальных месяцев {n_uniq}"),
        ("месяцы совпадают с данными orders_enriched", n_rows == expected_months,
         f"ожидалось {expected_months} месяцев, получено {n_rows} – "
         "проверьте, что считаете от orders_enriched и не теряете месяцы"),
        ("сумма n_orders = числу заказов", orders_sum == orders_src,
         f"ожидалось {orders_src:,}, получено {orders_sum:,}"),
        ("сумма revenue = выручке в orders_enriched",
         abs(total_rev - src_rev) < 1.0,
         f"ожидалось {src_rev:,.2f}, получено {total_rev:,.2f}"),
        ("накопительный итог считается корректно в каждой строке", bad_cum == 0,
         f"строк с неверным revenue_cumulative: {bad_cum}. "
         "Накопительный итог – это сумма всех предыдущих месяцев включительно"),
        ("в последнем месяце накопительный итог = всей выручке",
         abs(last_cum - total_rev) < 1.0,
         f"последнее значение {last_cum:,.2f} против суммы {total_rev:,.2f}"),
        ("revenue_prev соответствует предыдущему месяцу", bad_lag == 0,
         f"строк с неверным revenue_prev: {bad_lag}"),
        ("накопительный итог написан через SQL оконную функцию",
         _uses_window_function(sql),
         "в тексте вашего SQL не найдена конструкция `... OVER (...)`. "
         "Посчитайте накопительный итог и предыдущий месяц оконными функциями"),
    ]
    return check(lab, item, rows, title="Задание 2: monthly_revenue")


def lab02_result() -> bool:
    return lab_result(
        "lab02",
        [("task_1", "orders_enriched: одна строка на заказ, суммы сходятся"),
         ("task_2", "monthly_revenue: оконный накопительный итог")],
        artifacts=[("хранилище data/processed/warehouse.duckdb", WAREHOUSE),
                   ("data/staging/lab02_orders_enriched.parquet",
                    STAGING / "lab02_orders_enriched.parquet")],
    )
