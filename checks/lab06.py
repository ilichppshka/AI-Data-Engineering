"""Проверки к ЛР 6."""
from __future__ import annotations

import pandas as pd

from checks._reference import SQL
from checks.common import check, lab_result, record
from paths import MARTS

FEATURE_COLS = ["order_id", "order_date", "n_items", "items_total", "freight_total",
                "n_sellers", "n_categories", "total_weight_g", "seller_state",
                "customer_state", "same_state", "estimated_days", "purchase_month",
                "purchase_dow", "payment_total", "installments", "payment_type",
                "is_late"]

# признаки, которых не существует в момент оформления заказа
LEAKY = ["delivery_days", "order_delivered_customer_date",
         "order_delivered_carrier_date", "is_delivered", "review_score",
         "order_status", "order_approved_at", "delivered_at", "actual_days"]


def _fail(lab, item, title, msg):
    record(lab, item, False, msg)
    print(f"── {title} " + "─" * max(0, 62 - len(title)))
    print(f" ✗ {msg}\n")
    return None


# ----------------------------------------------------------------- задание 1
def check_task_1(con, part_dir):
    lab, item, title = "lab06", "task_1", "Задание 1: партиционирование"
    parts = sorted(p for p in part_dir.glob("year_month=*") if p.is_dir())
    if not parts:
        return _fail(lab, item, title,
                     f"в {part_dir} не найдено ни одной партиции вида year_month=YYYY-MM")

    glob = (part_dir / "**" / "*.parquet").as_posix()
    got = con.execute(f"""
        SELECT year_month, COUNT(*) AS n, ROUND(SUM(price), 2) AS s
        FROM read_parquet('{glob}', hive_partitioning = 1)
        GROUP BY 1 ORDER BY 1
    """).df()
    ref = con.execute(SQL["partitions"]).df()

    merged = ref.merge(got, on="year_month", how="outer", suffixes=("_ref", "_got"))
    bad_cells = int(((merged["n_ref"] != merged["n_got"])
                     | ((merged["s_ref"] - merged["s_got"]).abs() > 0.05)).sum())

    # внутри партиции должны лежать только строки своего месяца
    mixed = int(con.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{glob}', hive_partitioning = 1)
        WHERE strftime(order_date, '%Y-%m') <> year_month
    """).fetchone()[0])

    rows = [
        (f"число партиций = числу месяцев ({len(ref)})", len(parts) == len(ref),
         f"создано партиций: {len(parts)}. Проверьте ключ партиционирования"),
        ("все строки факта попали в партиции",
         int(got["n"].sum()) == int(ref["n"].sum()),
         f"в партициях {int(got['n'].sum()):,} строк, в факте {int(ref['n'].sum()):,}"),
        ("данные каждой партиции совпадают с фактом", bad_cells == 0,
         f"расходится месяцев: {bad_cells}"),
        ("внутри партиции только строки своего месяца", mixed == 0,
         f"строк не из своего месяца: {mixed:,}"),
    ]
    return check(lab, item, rows, title=title)


# ----------------------------------------------------------------- задание 2
def check_task_2(state, events_df: pd.DataFrame, topic):
    lab, item, title = "lab06", "task_2", "Задание 2: идемпотентный consumer"
    if not isinstance(state, dict) or "n_events" not in state:
        return _fail(lab, item, title, "состояние обработчика пустое или неверной формы")

    uniq = events_df.drop_duplicates(subset="event_id")
    exp_n = int(len(uniq))
    exp_total = float(uniq["amount"].sum())
    exp_by_type = uniq.groupby("payment_type")["amount"].sum().round(2).to_dict()
    got_by_type = {k: round(float(v), 2) for k, v in state.get("by_type", {}).items()}
    type_bad = sorted(k for k in set(exp_by_type) | set(got_by_type)
                      if abs(exp_by_type.get(k, 0) - got_by_type.get(k, 0)) > 0.5)

    rows = [
        ("в топике действительно были дубликаты (проверка осмысленна)",
         len(topic) > exp_n, "источник не продублировал ни одного события"),
        (f"обработано ровно {exp_n:,} уникальных событий",
         int(state["n_events"]) == exp_n,
         f"получилось {int(state['n_events']):,}. Если больше – повторные "
         "доставки посчитаны как новые события; ключ идемпотентности "
         "должен однозначно определять событие"),
        (f"сумма по уникальным событиям = {exp_total:,.2f}",
         abs(float(state.get("total_amount", 0)) - exp_total) < 1.0,
         f"получено {float(state.get('total_amount', 0)):,.2f}"),
        ("суммы по типам оплаты совпадают", not type_bad,
         f"расходятся типы: {type_bad}"),
        ("обработчик помнит, что уже видел",
         len(state.get("seen", ())) == exp_n,
         f"в state['seen'] {len(state.get('seen', ())):,} ключей, "
         f"ожидалось {exp_n:,}"),
    ]
    return check(lab, item, rows, title=title)


# ----------------------------------------------------------------- задание 3
def check_task_3(features, metrics: dict, con):
    lab, item, title = "lab06", "task_3", "Задание 3: признаки без утечки"
    if not isinstance(features, pd.DataFrame) or features.empty:
        return _fail(lab, item, title, "таблица признаков не построена")

    missing = [c for c in FEATURE_COLS if c not in features.columns]
    if missing:
        return check(lab, item, [("есть все колонки контракта", False,
                                  f"не хватает: {missing}")], title=title)

    leaks = [c for c in features.columns if c.lower() in LEAKY]
    exp_rows = int(con.execute(SQL["feature_rows"]).fetchone()[0])
    exp_late = float(con.execute(SQL["feature_late_rate"]).fetchone()[0])

    feat_cols = [c for c in features.columns if c not in ("order_id", "order_date")]
    nan_cols = [c for c in feat_cols if features[c].isna().any()]
    target_ok = set(pd.unique(features["is_late"].dropna())) <= {0, 1, True, False}
    auc = float(metrics.get("auc", 0))

    rows = [
        ("одна строка на заказ", bool(features["order_id"].is_unique),
         "позиции заказа нужно агрегировать до уровня заказа, иначе "
         "многопозиционные заказы попадут в обучение несколько раз"),
        (f"строк = числу доставленных заказов ({exp_rows:,})",
         len(features) == exp_rows,
         f"получилось {len(features):,}"),
        ("нет признаков, которых не существует в момент заказа", not leaks,
         f"найдены признаки из будущего: {leaks}. Они вычисляются из даты "
         "доставки – то есть из того, что мы и пытаемся предсказать"),
        ("нет пропусков в признаках", not nan_cols,
         f"пропуски в колонках: {nan_cols}"),
        ("ответ is_late принимает значения 0/1", bool(target_ok), ""),
        (f"доля опоздавших близка к данным ({exp_late:.3%})",
         abs(float(features["is_late"].mean()) - exp_late) < 0.01,
         f"в таблице признаков {float(features['is_late'].mean()):.3%}"),
        ("обучающая и валидационная части непусты",
         int(metrics.get("n_train", 0)) > 0 and int(metrics.get("n_valid", 0)) > 0,
         f"train={metrics.get('n_train')}, valid={metrics.get('n_valid')}"),
        (f"AUC модели правдоподобен: 0.55 < {auc:.3f} < 0.95",
         0.55 < auc < 0.95,
         "AUC около единицы почти всегда означает утечку ответа, "
         "AUC около 0.5 – что признаки не несут сигнала"),
    ]
    return check(lab, item, rows, title=title)


def lab06_result() -> bool:
    return lab_result(
        "lab06",
        [("task_1", "партиционированная копия факта"),
         ("task_2", "идемпотентный обработчик потока событий"),
         ("task_3", "таблица признаков без утечки и обученная модель")],
        artifacts=[("data/marts/fact_partitioned/", MARTS / "fact_partitioned"),
                   ("data/marts/features_orders.parquet",
                    MARTS / "features_orders.parquet"),
                   ("data/marts/model_metrics.parquet",
                    MARTS / "model_metrics.parquet")],
    )
