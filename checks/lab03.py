"""Проверки к ЛР 3.

Все эталонные значения пересчитываются из RAW прямо здесь, поэтому проверки
не зависят от того, какая версия датасета скачалась.
"""
from __future__ import annotations

import pandas as pd

from checks._reference import (DATE_COLS, order_violation_masks,
                               payments_expected, reviews_latest)
from checks.common import check, lab_result, record
from paths import CLEAN, QUALITY
CLEAN_ORDER_COLS = DATE_COLS + ["order_id", "customer_id", "order_status",
                                "is_delivered", "delivery_days", "is_late"]
PAYMENT_TYPES = {"credit_card", "boleto", "voucher", "debit_card"}


def _fail(lab, item, title, msg):
    record(lab, item, False, msg)
    print(f"── {title} " + "─" * max(0, 62 - len(title)))
    print(f" ✗ {msg}\n")
    return None




# ----------------------------------------------------------------- задание 1
def check_task_1(clean, quarantine, raw):
    lab, item, title = "lab03", "task_1", "Задание 1: clean_orders"
    if not isinstance(clean, pd.DataFrame) or clean.empty:
        return _fail(lab, item, title, "clean_orders не построена")
    missing = [c for c in CLEAN_ORDER_COLS if c not in clean.columns]
    if missing:
        return check(lab, item, [("есть все колонки контракта", False,
                                  f"не хватает: {missing}")], title=title)

    masks = order_violation_masks(raw)
    bad_any = masks["R1"] | masks["R2"] | masks["R3"] | masks["R4"]
    exp_clean, exp_quar = int((~bad_any).sum()), int(bad_any.sum())

    clean_masks = order_violation_masks(clean)
    left_bad = int((clean_masks["R1"] | clean_masks["R2"]
                    | clean_masks["R3"] | clean_masks["R4"]).sum())

    dt_ok = all(pd.api.types.is_datetime64_any_dtype(clean[c]) for c in DATE_COLS)

    ref = clean.copy()
    delivered = ref["order_status"] == "delivered"
    exp_days = ((pd.to_datetime(ref["order_delivered_customer_date"])
                 - pd.to_datetime(ref["order_purchase_timestamp"])).dt.days).where(delivered)
    got_days = pd.to_numeric(ref["delivery_days"], errors="coerce")
    days_ok = bool(((got_days.isna() & exp_days.isna())
                    | ((got_days - exp_days).abs() <= 0.01)).all())

    exp_late = (pd.to_datetime(ref["order_delivered_customer_date"])
                > pd.to_datetime(ref["order_estimated_delivery_date"])).where(delivered)
    got_late = ref["is_late"]
    late_ok = bool(((got_late.isna() & exp_late.isna())
                    | (got_late.astype("object") == exp_late.astype("object"))).all())
    late_na_ok = bool(got_late[~delivered].isna().all())

    deliv_ok = bool((ref["is_delivered"].astype(bool) == delivered).all())

    q_ok = isinstance(quarantine, pd.DataFrame) and "reason" in getattr(
        quarantine, "columns", [])
    q_len = len(quarantine) if isinstance(quarantine, pd.DataFrame) else -1

    rows = [
        (f"в clean_orders {exp_clean:,} строк (RAW минус карантин)",
         len(clean) == exp_clean,
         f"получилось {len(clean):,}; нарушители критических правил должны "
         "уйти в карантин, а остальные строки – остаться"),
        ("order_id уникален и без пропусков",
         bool(clean["order_id"].is_unique and clean["order_id"].notna().all()), ""),
        ("все пять дат имеют тип datetime", dt_ok,
         "какая-то из колонок дат осталась строкой – приведите тип явно"),
        ("в clean не осталось нарушителей R1–R4", left_bad == 0,
         f"нарушающих строк осталось: {left_bad}"),
        (f"в карантине {exp_quar:,} строк и есть колонка reason",
         q_ok and q_len == exp_quar,
         f"в карантине {q_len} строк, ожидалось {exp_quar}; "
         "колонка reason обязательна – иначе непонятно, почему строку отбраковали"),
        ("строки не потерялись: clean + карантин = RAW",
         len(clean) + max(q_len, 0) == len(raw),
         f"{len(clean):,} + {max(q_len, 0):,} ≠ {len(raw):,}"),
        ("is_delivered соответствует статусу", deliv_ok, ""),
        ("delivery_days: полные сутки доставки, NaN у недоставленных", days_ok,
         "значения не совпадают с разностью дат доставки и покупки "
         "(или заполнены там, где заказ не доставлен)"),
        ("is_late: доставлен позже обещанной даты", late_ok,
         "значение не совпадает со сравнением фактической и обещанной дат"),
        ("is_late пуст у недоставленных заказов", late_na_ok,
         "у недоставленного заказа не может быть признака опоздания"),
    ]
    return check(lab, item, rows, title=title)


# ----------------------------------------------------------------- задание 2
def check_task_2(clean, quarantine, raw):
    lab, item, title = "lab03", "task_2", "Задание 2: clean_payments"
    if not isinstance(clean, pd.DataFrame) or clean.empty:
        return _fail(lab, item, title, "clean_payments не построена")

    expected = payments_expected(raw)
    exp_clean, exp_quar = expected["rows"], expected["quarantine"]
    exp_sum = expected["total"]

    got_sum = float(clean["payment_value"].sum())
    grain_ok = not clean.duplicated(subset=["order_id", "payment_sequential"]).any()
    bad_left = int(((clean["payment_value"] <= 0)
                    | (~clean["payment_type"].isin(PAYMENT_TYPES))).sum())
    q_len = len(quarantine) if isinstance(quarantine, pd.DataFrame) else -1
    int_ok = pd.api.types.is_integer_dtype(clean["payment_installments"])
    n_orders_ok = clean["order_id"].nunique() == expected["orders"]

    rows = [
        (f"строк в clean_payments = {exp_clean:,}", len(clean) == exp_clean,
         f"получилось {len(clean):,}. Если строк заметно меньше – вы удалили "
         "не дубликаты, а законные платёжные операции по одному заказу"),
        ("ключ (order_id, payment_sequential) уникален", grain_ok,
         "ключ таблицы платежей – пара «заказ + номер операции»"),
        (f"сумма платежей = {exp_sum:,.2f}", abs(got_sum - exp_sum) < 1.0,
         f"получено {got_sum:,.2f}; расхождение {got_sum - exp_sum:,.2f} – "
         "часть платежей потеряна или посчитана дважды"),
        ("в clean нет строк с нарушением правил", bad_left == 0,
         f"осталось строк с нулевой суммой или недопустимым типом: {bad_left}"),
        (f"в карантине {exp_quar} строк", q_len == exp_quar,
         f"в карантине {q_len}"),
        ("payment_installments – целое число", int_ok, "приведите тип явно"),
        ("не потеряно ни одного заказа с платежами", n_orders_ok,
         "число заказов в clean_payments меньше, чем в RAW после отбраковки"),
    ]
    return check(lab, item, rows, title=title)


# ----------------------------------------------------------------- задание 3
def check_task_3(clean, raw):
    lab, item, title = "lab03", "task_3", "Задание 3: clean_reviews"
    if not isinstance(clean, pd.DataFrame) or clean.empty:
        return _fail(lab, item, title, "clean_reviews не построена")
    need = ["review_id", "order_id", "review_score",
            "review_creation_date", "review_answer_timestamp"]
    missing = [c for c in need if c not in clean.columns]
    if missing:
        return check(lab, item, [("есть все колонки контракта", False,
                                  f"не хватает: {missing}")], title=title)

    exp_orders = int(raw["order_id"].nunique())
    lost = exp_orders - clean["order_id"].nunique()

    latest = reviews_latest(raw)
    got = clean.set_index("order_id")["review_answer_timestamp"]
    got = pd.to_datetime(got, errors="coerce")
    aligned = latest.reindex(got.index)
    rule_bad = int((got != aligned).sum())

    score_ok = bool(pd.to_numeric(clean["review_score"], errors="coerce")
                    .between(1, 5).all())
    dt_ok = (pd.api.types.is_datetime64_any_dtype(clean["review_creation_date"])
             and pd.api.types.is_datetime64_any_dtype(clean["review_answer_timestamp"]))

    rows = [
        ("order_id уникален – один отзыв на заказ",
         bool(clean["order_id"].is_unique), "в таблице есть заказы с двумя отзывами"),
        (f"сохранены все {exp_orders:,} заказов с отзывами", lost == 0,
         f"потеряно заказов: {lost}. Скорее всего, вы удалили строки по "
         "review_id – но одинаковый review_id у РАЗНЫХ заказов дубликатом "
         "при этом зерне не является"),
        (f"строк ровно {exp_orders:,}", len(clean) == exp_orders,
         f"получилось {len(clean):,}"),
        ("правило разрешения конфликта: оставлен последний отзыв по времени ответа",
         rule_bad == 0,
         f"строк с «не последним» отзывом: {rule_bad}"),
        ("review_score – целое от 1 до 5", score_ok, ""),
        ("даты отзывов имеют тип datetime", dt_ok, ""),
    ]
    return check(lab, item, rows, title=title)


def lab03_result() -> bool:
    return lab_result(
        "lab03",
        [("task_1", "clean_orders: типы, бизнес-правила, карантин"),
         ("task_2", "clean_payments: ошибка коллеги найдена и исправлена"),
         ("task_3", "clean_reviews: зерно определено, заказы не потеряны")],
        artifacts=[("data/staging/clean/clean_orders.parquet", CLEAN / "clean_orders.parquet"),
                   ("data/staging/clean/clean_payments.parquet", CLEAN / "clean_payments.parquet"),
                   ("data/staging/clean/clean_reviews.parquet", CLEAN / "clean_reviews.parquet"),
                   ("data/staging/clean/clean_items.parquet", CLEAN / "clean_items.parquet"),
                   ("отчёт о качестве data/quality/lab03_report.json",
                    QUALITY / "lab03_report.json")],
    )
