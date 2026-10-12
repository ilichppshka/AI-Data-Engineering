"""Механика проверок.

Каждая проверка печатает, что сошлось и что нет, и откладывает результат
в data/_runs, чтобы сводку было видно и после перезапуска ядра.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from paths import RUNS, ensure_dirs                       # noqa: E402

OK, BAD, WARN = "✓", "✗", "!"


# --------------------------------------------------------------------------- IO
def _file(lab: str) -> Path:
    ensure_dirs()
    return RUNS / f"{lab}_checks.json"


def _load(lab: str) -> dict:
    p = _file(lab)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def record(lab: str, item: str, passed: bool, detail: str = "") -> None:
    data = _load(lab)
    data[item] = {"passed": bool(passed), "detail": detail,
                  "ts": datetime.now().isoformat(timespec="seconds")}
    _file(lab).write_text(json.dumps(data, ensure_ascii=False, indent=1),
                          encoding="utf-8")


def load_results(lab: str) -> dict:
    return _load(lab)


def reset(lab: str) -> None:
    p = _file(lab)
    if p.exists():
        p.unlink()


# ---------------------------------------------------------------------- вывод
class Result:
    """Итог одной проверки: печатается и умеет вести себя как bool."""

    def __init__(self, item: str, rows: list[tuple[str, bool, str]]):
        self.item = item
        self.rows = rows
        self.passed = all(r[1] for r in rows)

    def __bool__(self) -> bool:
        return self.passed

    def __repr__(self) -> str:
        return f"<{self.item}: {'OK' if self.passed else 'FAILED'}>"


def check(lab: str, item: str, rows: list[tuple[str, bool, str]],
          title: str | None = None) -> Result:
    """
    rows: список (описание, условие, подсказка_если_не_прошло)
    Подсказка объясняет, ЧТО не так, но не выдаёт готовый ответ.
    """
    res = Result(item, rows)
    head = title or item
    print(f"── {head} " + "─" * max(0, 62 - len(head)))
    for desc, passed, hint in rows:
        print(f" {OK if passed else BAD} {desc}")
        if not passed and hint:
            for line in str(hint).splitlines():
                print(f"     → {line}")
    print(f" {'ВЫПОЛНЕНО' if res.passed else 'ЕСТЬ ЧТО ИСПРАВИТЬ'}: "
          f"{sum(1 for r in rows if r[1])}/{len(rows)}\n")
    record(lab, item, res.passed,
           "; ".join(d for d, p, _ in rows if not p))
    return res


def lab_result(lab: str, expected_items: list[tuple[str, str]],
               artifacts: list[tuple[str, Path]] | None = None) -> bool:
    """
    Финальный блок для преподавателя.
    expected_items: [(ключ, человеческое описание), ...]
    artifacts:      [(описание, путь), ...] – файлы, которые должны появиться
    """
    data = _load(lab)
    number = lab.replace("lab", "").lstrip("0") or "0"
    print("=" * 66)
    print(f"ИТОГ РАБОТЫ {number}".center(66))
    print("=" * 66)
    done = 0
    for key, desc in expected_items:
        st = data.get(key)
        if st is None:
            print(f" {BAD} {desc}  (проверка не запускалась)")
        elif st["passed"]:
            print(f" {OK} {desc}")
            done += 1
        else:
            print(f" {BAD} {desc}")
            if st.get("detail"):
                print(f"     → {st['detail']}")
    if artifacts:
        print("-" * 66)
        for desc, path in artifacts:
            exists = Path(path).exists()
            print(f" {OK if exists else BAD} артефакт: {desc}")
            if not exists:
                print(f"     → ожидался файл {path}")
    total = len(expected_items)
    print("-" * 66)
    print(f" Выполнено проверок: {done}/{total}")
    if done == total:
        print(" Статус: работа выполнена")
    elif done >= total * 0.5:
        print(" Статус: выполнена частично")
    else:
        print(" Статус: есть принципиальные ошибки")
    print("=" * 66)
    return done == total


# ------------------------------------------------------- вспомогательные вещи
def approx(a: float, b: float, tol: float = 0.01) -> bool:
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))


def has_columns(df, cols) -> tuple[bool, str]:
    missing = [c for c in cols if c not in df.columns]
    return (not missing, f"не хватает колонок: {missing}" if missing else "")
