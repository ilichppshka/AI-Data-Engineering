"""Проверки к ЛР 4.

Эталоны считаются независимым SQL прямо здесь, от слоя CLEAN и измерений,
поэтому проверка не зависит от того, как именно студент написал запрос.
"""
from __future__ import annotations

from checks._reference import SQL
from checks.common import check, lab_result, record
from paths import MARTS, WAREHOUSE

FACT_COLS = ["order_id", "order_item_id", "date_key", "order_date", "customer_id",
             "product_id", "seller_id", "price", "freight_value", "order_status",
             "is_delivered", "is_late", "delivery_days"]
M1_COLS = ["month", "category_en", "revenue", "n_items", "n_orders", "avg_review_score"]
M2_COLS = ["month", "seller_state", "n_orders", "n_late_orders", "late_share",
           "avg_delivery_days"]




def _exists(con, schema: str, name: str) -> bool:
    return bool(con.execute(
        "SELECT COUNT(*) FROM duckdb_tables() WHERE schema_name = ? AND table_name = ?",
        [schema, name]).fetchone()[0])


def _cols(con, full_name: str) -> list[str]:
    return [r[0] for r in con.execute(f"DESCRIBE {full_name}").fetchall()]


def _one(con, sql: str):
    return con.execute(sql).fetchone()[0]


def _fail(lab, item, title, msg):
    record(lab, item, False, msg)
    print(f"── {title} " + "─" * max(0, 62 - len(title)))
    print(f" ✗ {msg}\n")
    return None


def _compare(con, student_sql: str, ref_sql: str, keys: list[str],
             numeric: list[str], tol: float = 0.01) -> tuple[int, int, int]:
    """Возвращает (строк у студента, строк в эталоне, число расхождений)."""
    on = " AND ".join(f"s.{k} IS NOT DISTINCT FROM r.{k}" for k in keys)
    diff = " OR ".join(
        f"(s.{c} IS NULL) <> (r.{c} IS NULL) OR abs(COALESCE(s.{c},0) - COALESCE(r.{c},0)) > {tol}"
        for c in numeric)
    n_s = _one(con, f"SELECT COUNT(*) FROM ({student_sql}) s")
    n_r = _one(con, f"SELECT COUNT(*) FROM ({ref_sql}) r")
    n_bad = _one(con, f"""
        SELECT COUNT(*) FROM ({student_sql}) s
        FULL OUTER JOIN ({ref_sql}) r ON {on}
        WHERE s.{keys[0]} IS NULL OR r.{keys[0]} IS NULL OR {diff}
    """)
    return int(n_s), int(n_r), int(n_bad)


# ----------------------------------------------------------------- задание 1
def check_task_1(con):
    lab, item, title = "lab04", "task_1", "Задание 1: core.fact_order_items"
    if not _exists(con, "core", "fact_order_items"):
        return _fail(lab, item, title, "таблица core.fact_order_items не создана")
    cols = _cols(con, "core.fact_order_items")
    missing = [c for c in FACT_COLS if c not in cols]
    if missing:
        return check(lab, item, [("есть все колонки контракта", False,
                                  f"не хватает: {missing}")], title=title)

    exp_rows = int(_one(con, SQL["fact_rows"]))
    exp_price = float(_one(con, SQL["fact_price"]))
    exp_freight = float(_one(con, SQL["fact_freight"]))

    n_rows = int(_one(con, "SELECT COUNT(*) FROM core.fact_order_items"))
    n_key = int(_one(con, """
        SELECT COUNT(*) FROM (SELECT DISTINCT order_id, order_item_id
                              FROM core.fact_order_items)"""))
    price = float(_one(con, "SELECT SUM(price) FROM core.fact_order_items") or 0)
    freight = float(_one(con, "SELECT SUM(freight_value) FROM core.fact_order_items") or 0)

    orphan_p = int(_one(con, """
        SELECT COUNT(*) FROM core.fact_order_items f
        LEFT JOIN core.dim_product d USING (product_id) WHERE d.product_id IS NULL"""))
    orphan_s = int(_one(con, """
        SELECT COUNT(*) FROM core.fact_order_items f
        LEFT JOIN core.dim_seller d USING (seller_id) WHERE d.seller_id IS NULL"""))
    orphan_c = int(_one(con, """
        SELECT COUNT(*) FROM core.fact_order_items f
        LEFT JOIN core.dim_customer d USING (customer_id) WHERE d.customer_id IS NULL"""))
    orphan_d = int(_one(con, """
        SELECT COUNT(*) FROM core.fact_order_items f
        LEFT JOIN core.dim_date d USING (date_key) WHERE d.date_key IS NULL"""))
    bad_key = int(_one(con, """
        SELECT COUNT(*) FROM core.fact_order_items
        WHERE date_key <> CAST(strftime(order_date, '%Y%m%d') AS INTEGER)"""))
    nulls = int(_one(con, """
        SELECT COUNT(*) FROM core.fact_order_items
        WHERE price IS NULL OR freight_value IS NULL OR order_id IS NULL"""))

    rows = [
        (f"строк ровно {exp_rows:,} (позиции заказов из clean_orders)",
         n_rows == exp_rows,
         f"получилось {n_rows:,}. Больше – соединение размножило позиции; "
         "меньше – потеряны позиции или использован лишний фильтр"),
        ("ключ (order_id, order_item_id) уникален", n_key == n_rows,
         f"уникальных пар {n_key:,} при {n_rows:,} строках"),
        (f"сумма price = {exp_price:,.2f}", abs(price - exp_price) < 1.0,
         f"получено {price:,.2f}"),
        (f"сумма freight_value = {exp_freight:,.2f}", abs(freight - exp_freight) < 1.0,
         f"получено {freight:,.2f}"),
        ("все product_id есть в dim_product", orphan_p == 0,
         f"строк без товара в измерении: {orphan_p:,}"),
        ("все seller_id есть в dim_seller", orphan_s == 0,
         f"строк без продавца в измерении: {orphan_s:,}"),
        ("все customer_id есть в dim_customer", orphan_c == 0,
         f"строк без клиента в измерении: {orphan_c:,}"),
        ("все date_key есть в dim_date", orphan_d == 0,
         f"строк без даты в календаре: {orphan_d:,}"),
        ("date_key соответствует order_date", bad_key == 0,
         f"несогласованных строк: {bad_key:,}"),
        ("нет NULL в ключах и мерах", nulls == 0, f"строк с NULL: {nulls:,}"),
    ]
    return check(lab, item, rows, title=title)


# ----------------------------------------------------------------- задание 2
def check_task_2(con):
    lab, item, title = "lab04", "task_2", "Задание 2: mart.mart_category_month"
    if not _exists(con, "mart", "mart_category_month"):
        return _fail(lab, item, title, "таблица mart.mart_category_month не создана")
    cols = _cols(con, "mart.mart_category_month")
    missing = [c for c in M1_COLS if c not in cols]
    if missing:
        return check(lab, item, [("есть все колонки контракта", False,
                                  f"не хватает: {missing}")], title=title)

    n_s, n_r, n_bad = _compare(
        con, "SELECT * FROM mart.mart_category_month", SQL["category_month"],
        keys=["month", "category_en"],
        numeric=["revenue", "n_items", "n_orders", "avg_review_score"])

    grain_ok = n_s == int(_one(con, """
        SELECT COUNT(*) FROM (SELECT DISTINCT month, category_en
                              FROM mart.mart_category_month)"""))
    total_rev = float(_one(con, "SELECT SUM(revenue) FROM mart.mart_category_month") or 0)
    exp_rev = float(_one(con, SQL["category_month_revenue"]))
    score_ok = int(_one(con, """
        SELECT COUNT(*) FROM mart.mart_category_month
        WHERE avg_review_score IS NOT NULL
          AND (avg_review_score < 1 OR avg_review_score > 5)""")) == 0

    rows = [
        ("зерно витрины: (месяц, категория) уникальны", grain_ok,
         "одна и та же пара месяц+категория встречается несколько раз"),
        (f"число строк совпадает с эталоном ({n_r:,})", n_s == n_r,
         f"получилось {n_s:,}"),
        (f"сумма revenue = {exp_rev:,.2f}", abs(total_rev - exp_rev) < 1.0,
         f"получено {total_rev:,.2f}"),
        ("все ячейки витрины совпадают с эталоном", n_bad == 0,
         f"расходится ячеек: {n_bad:,}. Чаще всего причина в avg_review_score: "
         "отзыв относится к заказу, а строки факта – к позициям, поэтому заказ "
         "с несколькими позициями получает лишний вес"),
        ("avg_review_score в диапазоне 1..5", score_ok, ""),
    ]
    return check(lab, item, rows, title=title)


# ----------------------------------------------------------------- задание 3
def check_task_3(con):
    lab, item, title = "lab04", "task_3", "Задание 3: mart.mart_seller_delivery"
    if not _exists(con, "mart", "mart_seller_delivery"):
        return _fail(lab, item, title, "таблица mart.mart_seller_delivery не создана")
    cols = _cols(con, "mart.mart_seller_delivery")
    missing = [c for c in M2_COLS if c not in cols]
    if missing:
        return check(lab, item, [("есть все колонки контракта", False,
                                  f"не хватает: {missing}")], title=title)

    n_s, n_r, n_bad = _compare(
        con, "SELECT * FROM mart.mart_seller_delivery", SQL["seller_delivery"],
        keys=["month", "seller_state"],
        numeric=["n_orders", "n_late_orders", "late_share", "avg_delivery_days"])

    share_ok = int(_one(con, """
        SELECT COUNT(*) FROM mart.mart_seller_delivery
        WHERE late_share < 0 OR late_share > 1""")) == 0
    only_delivered = int(_one(con, """
        SELECT COUNT(*) FROM mart.mart_seller_delivery WHERE n_orders <= 0""")) == 0
    total_orders = int(_one(con, "SELECT SUM(n_orders) FROM mart.mart_seller_delivery") or 0)
    delivered_orders = int(_one(con, SQL["delivered_orders"]))

    rows = [
        (f"число строк совпадает с эталоном ({n_r:,})", n_s == n_r,
         f"получилось {n_s:,}"),
        ("все ячейки витрины совпадают с эталоном", n_bad == 0,
         f"расходится ячеек: {n_bad:,}. Проверьте, что заказ учитывается "
         "один раз на штат (а не по числу позиций) и что фильтр по "
         "доставленным заказам применён"),
        ("late_share в диапазоне 0..1", share_ok, ""),
        ("нет строк с нулевым числом заказов", only_delivered, ""),
        ("сумма n_orders по штатам ≥ числа доставленных заказов "
         "(мультиштатные заказы учтены дважды осознанно)",
         total_orders >= delivered_orders,
         f"сумма {total_orders:,} < {delivered_orders:,} – часть заказов потеряна"),
    ]
    return check(lab, item, rows, title=title)


def lab04_result() -> bool:
    return lab_result(
        "lab04",
        [("task_1", "core.fact_order_items: зерно позиции, ссылочная целостность"),
         ("task_2", "mart.mart_category_month: витрина категорий и отзывов"),
         ("task_3", "mart.mart_seller_delivery: витрина под новое требование")],
        artifacts=[("хранилище data/processed/warehouse.duckdb", WAREHOUSE),
                   ("data/marts/mart_category_month.parquet",
                    MARTS / "mart_category_month.parquet"),
                   ("data/marts/mart_seller_delivery.parquet",
                    MARTS / "mart_seller_delivery.parquet")],
    )
