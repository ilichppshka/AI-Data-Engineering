"""Проверки к ЛР 5.

Особенность: эти проверки не смотрят на код – они **запускают pipeline**
и наблюдают за поведением. Идемпотентность нельзя проверить чтением исходника,
её можно только выполнить дважды и сравнить результат.
"""
from __future__ import annotations

from checks._reference import PIPELINE_EDGES, SQL
from checks.common import check, lab_result, record
from paths import LOGS, RUNS, WAREHOUSE

REQUIRED_TASKS = ["prepare", "ingest", "validate", "transform", "build_mart", "check"]
EDGES = [("prepare", "ingest"), ("ingest", "validate"), ("validate", "transform"),
         ("transform", "build_mart"), ("build_mart", "check")]

SNAPSHOT_SQL = """
    SELECT COUNT(*) AS days,
           ROUND(COALESCE(SUM(revenue), 0), 2)  AS revenue,
           ROUND(COALESCE(SUM(freight), 0), 2)  AS freight,
           COALESCE(SUM(n_orders), 0)           AS n_orders,
           COALESCE(SUM(n_items), 0)            AS n_items
    FROM mart.daily_sales
"""


def _fail(lab, item, title, msg):
    record(lab, item, False, msg)
    print(f"── {title} " + "─" * max(0, 62 - len(title)))
    print(f" ✗ {msg}\n")
    return None


def _upstream(pipe, name: str) -> set[str]:
    """Все задачи, от которых task зависит транзитивно."""
    seen, stack = set(), list(pipe.tasks[name].depends_on)
    while stack:
        cur = stack.pop()
        if cur in seen or cur not in pipe.tasks:
            continue
        seen.add(cur)
        stack.extend(pipe.tasks[cur].depends_on)
    return seen


def _snapshot(con) -> tuple:
    return tuple(con.execute(SNAPSHOT_SQL).fetchone())


def _diff_vs_reference(con, start: str, end: str) -> int:
    """Сколько дней в витрине расходится с прямым расчётом по факту."""
    sql = SQL["daily_sales_diff"].format(start=start, end=end)
    return int(con.execute(sql).fetchone()[0])


# ----------------------------------------------------------------- задание 2
def check_task_2(pipe, result=None):
    lab, item, title = "lab05", "task_2", "Задание 2: DAG собран правильно"
    missing = [t for t in REQUIRED_TASKS if t not in pipe.tasks]
    if missing:
        return _fail(lab, item, title, f"в pipeline нет задач: {missing}")

    rows = []
    for up, down in PIPELINE_EDGES:
        ok = up in _upstream(pipe, down)
        rows.append((f"'{down}' выполняется после '{up}'", ok,
                     f"'{down}' не зависит от '{up}' ни напрямую, ни через другие "
                     "задачи – подумайте, какие данные нужны этому шагу"))
    try:
        order = pipe.order()
        cyc_ok, hint = True, ""
    except Exception as exc:                                  # noqa: BLE001
        order, cyc_ok, hint = [], False, str(exc)
    rows.append(("DAG корректен (нет циклов и неизвестных зависимостей)", cyc_ok, hint))
    if result is not None:
        rows.append(("полный прогон pipeline завершился успешно",
                     getattr(result, "status", "") == "success",
                     "посмотрите, какая задача упала и почему: "
                     f"{ {k: v.status for k, v in getattr(result, 'tasks', {}).items()} }"))
    if order:
        print(f"   порядок выполнения: {' → '.join(order)}")
    return check(lab, item, rows, title=title)


# ----------------------------------------------------------------- задание 1
def check_task_1(pipe, con, window: dict):
    lab, item, title = "lab05", "task_1", "Задание 1: build_mart идемпотентен"
    start, end = window["start"], window["end"]
    ctx = {"con": con, "start": start, "end": end}

    r1 = pipe.quiet().run(ctx)
    if r1.status != "success":
        return _fail(lab, item, title,
                     "pipeline не отработал целиком, идемпотентность проверить "
                     f"нельзя: { {k: v.status for k, v in r1.tasks.items()} }")
    snap1 = _snapshot(con)
    r2 = pipe.run(ctx)
    snap2 = _snapshot(con)

    dup = int(con.execute("""
        SELECT COUNT(*) FROM (SELECT order_date FROM mart.daily_sales
                              GROUP BY order_date HAVING COUNT(*) > 1)
    """).fetchone()[0])
    diff = _diff_vs_reference(con, start, end)

    # «не трогай чужие периоды»: кладём строку вне окна и запускаем шаг за март
    con.execute("DELETE FROM mart.daily_sales WHERE order_date = DATE '2099-01-01'")
    con.execute("""INSERT INTO mart.daily_sales VALUES (DATE '2099-01-01', 1, 1, 0.0, 0.0)""")
    pipe.run({"con": con, "start": "2018-03-01", "end": "2018-03-31"},
             only=["build_mart"])
    sentinel = int(con.execute("""
        SELECT COUNT(*) FROM mart.daily_sales WHERE order_date = DATE '2099-01-01'
    """).fetchone()[0])
    con.execute("DELETE FROM mart.daily_sales WHERE order_date = DATE '2099-01-01'")

    rows = [
        ("второй запуск за тот же период не изменил витрину", snap1 == snap2,
         f"было {snap1}, стало {snap2} – шаг дописывает данные вместо того, "
         "чтобы замещать период"),
        ("в витрине нет повторяющихся дат", dup == 0,
         f"дат-дубликатов: {dup}"),
        ("значения витрины совпадают с прямым расчётом по факту", diff == 0,
         f"расходится дней: {diff}"),
        ("запуск за март не удалил данные других периодов", sentinel == 1,
         "шаг пересобирает всю таблицу целиком, а должен отвечать только "
         "за свой период – при инкрементальной загрузке так терять данные нельзя"),
        ("второй запуск завершился успешно", r2.status == "success", ""),
    ]
    return check(lab, item, rows, title=title)


# ----------------------------------------------------------------- задание 3
def check_task_3(pipe, con, window: dict, backfill: dict, tasks):
    lab, item, title = "lab05", "task_3", "Задание 3: backfill"
    if not backfill or str(backfill.get("start", "")).startswith("_") \
            or str(backfill.get("end", "")).startswith("_"):
        return _fail(lab, item, title, "период backfill не заполнен")
    if not tasks:
        return _fail(lab, item, title, "список задач для backfill пуст")

    start, end = str(backfill["start"]), str(backfill["end"])
    # эталонное состояние: полный прогон
    base = pipe.quiet().run({"con": con, **window})
    if base.status != "success":
        return _fail(lab, item, title,
                     "полный прогон pipeline падает, backfill проверить нельзя: "
                     f"{ {k: v.status for k, v in base.tasks.items()} }")
    full_snap = _snapshot(con)

    # портим март, как будто данные приехали неполными
    con.execute(f"""
        UPDATE mart.daily_sales SET revenue = revenue * 2, n_orders = n_orders + 7
        WHERE order_date BETWEEN DATE '{start}' AND DATE '{end}'
    """)
    broken_snap = _snapshot(con)

    res = pipe.run({"con": con, **backfill}, only=list(tasks))
    after = _snapshot(con)
    diff_window = _diff_vs_reference(con, start, end)
    diff_all = _diff_vs_reference(con, window["start"], window["end"])

    period_ok = (start[:7] == "2018-03" and end[:7] == "2018-03"
                 and start.endswith("-01") and end >= "2018-03-28")

    rows = [
        ("период backfill – март 2018", period_ok,
         f"указан период {start} … {end}"),
        ("backfill выполнился успешно", res.status == "success",
         f"статусы: { {k: v.status for k, v in res.tasks.items()} }"),
        ("данные за март восстановлены до корректных", diff_window == 0,
         f"расходится дней внутри периода: {diff_window}"),
        ("остальные периоды не пострадали", diff_all == 0,
         f"расходится дней во всей витрине: {diff_all}"),
        ("витрина вернулась к состоянию полного пересчёта",
         after == full_snap and broken_snap != full_snap,
         f"эталон {full_snap}, после backfill {after}"),
        ("в список задач backfill включён build_mart",
         "build_mart" in list(tasks),
         "без пересборки витрины backfill не имеет смысла"),
    ]
    return check(lab, item, rows, title=title)


def lab05_result() -> bool:
    return lab_result(
        "lab05",
        [("task_2", "DAG: зависимости расставлены, прогон успешен"),
         ("task_1", "build_mart идемпотентен и не трогает чужие периоды"),
         ("task_3", "backfill за март выполнен корректно")],
        artifacts=[("хранилище data/processed/warehouse.duckdb", WAREHOUSE),
                   ("метаданные запусков data/_runs/olist_daily_latest.json",
                    RUNS / "olist_daily_latest.json"),
                   ("лог logs/olist_daily.log", LOGS / "olist_daily.log")],
    )
