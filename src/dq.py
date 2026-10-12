"""Проверки качества данных.

Ожидания от таблицы описываются декларативно, движок считает, сколько строк
их нарушает, и собирает отчёт:

    report = (Suite("clean_orders")
              .not_null("order_id")
              .unique("order_id")
              .between("delivery_days", 0, 365)
              .run(df))
    report.raise_if_critical()

Уровень critical означает, что дальше ехать нельзя; warning – что нарушение
надо записать, но обработку можно продолжать.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd

CRITICAL = "critical"
WARNING = "warning"


@dataclass
class ExpectationResult:
    name: str
    severity: str
    n_bad: int
    n_rows: int
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.n_bad == 0

    @property
    def share(self) -> float:
        return self.n_bad / self.n_rows if self.n_rows else 0.0


@dataclass
class Report:
    table: str
    results: list[ExpectationResult] = field(default_factory=list)
    n_rows: int = 0

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def critical_failed(self) -> list[ExpectationResult]:
        return [r for r in self.results
                if not r.passed and r.severity == CRITICAL]

    def show(self) -> "Report":
        print(f"\nОтчёт о качестве: {self.table}  ({self.n_rows:,} строк)")
        print("-" * 72)
        for r in self.results:
            mark = "✓" if r.passed else ("✗" if r.severity == CRITICAL else "!")
            extra = "" if r.passed else f"  нарушений: {r.n_bad:,} ({r.share:.2%})"
            print(f" {mark} [{r.severity:8}] {r.name}{extra}")
            if not r.passed and r.detail:
                print(f"       {r.detail}")
        bad = sum(1 for r in self.results if not r.passed)
        print("-" * 72)
        print(f" пройдено {len(self.results) - bad}/{len(self.results)}; "
              f"критических нарушений: {len(self.critical_failed)}")
        return self

    def to_dict(self) -> dict:
        return {
            "table": self.table,
            "n_rows": self.n_rows,
            "passed": self.passed,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "expectations": [
                {"name": r.name, "severity": r.severity, "n_bad": r.n_bad,
                 "share": round(r.share, 6), "passed": r.passed,
                 "detail": r.detail}
                for r in self.results
            ],
        }

    def raise_if_critical(self) -> "Report":
        """Так ведёт себя шаг pipeline: критическое нарушение – это падение."""
        if self.critical_failed:
            names = "; ".join(r.name for r in self.critical_failed)
            raise DataQualityError(
                f"{self.table}: нарушены критические правила качества → {names}")
        return self


class DataQualityError(RuntimeError):
    """Данные не соответствуют контракту."""


class Suite:
    def __init__(self, table: str):
        self.table = table
        self._checks: list[tuple[str, str, Callable[[pd.DataFrame], pd.Series | int]]] = []

    # --- базовые ожидания -------------------------------------------------
    def not_null(self, col: str, severity: str = CRITICAL) -> "Suite":
        self._checks.append((f"{col}: нет пропусков", severity,
                             lambda df, c=col: df[c].isna()))
        return self

    def unique(self, cols: str | list[str], severity: str = CRITICAL) -> "Suite":
        cols_l = [cols] if isinstance(cols, str) else list(cols)
        name = f"{'+'.join(cols_l)}: уникален (grain таблицы)"
        self._checks.append((name, severity,
                             lambda df, c=cols_l: df.duplicated(subset=c, keep=False)))
        return self

    def in_set(self, col: str, values, severity: str = CRITICAL) -> "Suite":
        vals = set(values)
        self._checks.append((f"{col}: только допустимые значения", severity,
                             lambda df, c=col, v=vals: ~df[c].isin(v) & df[c].notna()))
        return self

    def between(self, col: str, lo=None, hi=None, allow_null: bool = True,
                severity: str = CRITICAL) -> "Suite":
        rng = f"[{lo if lo is not None else '-∞'}, {hi if hi is not None else '+∞'}]"

        def _bad(df, c=col, lo=lo, hi=hi, allow_null=allow_null):
            s = df[c]
            bad = pd.Series(False, index=df.index)
            if lo is not None:
                bad |= s < lo
            if hi is not None:
                bad |= s > hi
            if not allow_null:
                bad |= s.isna()
            return bad.fillna(False)

        self._checks.append((f"{col}: значения в диапазоне {rng}", severity, _bad))
        return self

    def foreign_key(self, col: str, ref: pd.DataFrame, ref_col: str,
                    severity: str = CRITICAL) -> "Suite":
        keys = set(ref[ref_col].dropna())
        self._checks.append(
            (f"{col} → {ref_col}: ссылочная целостность", severity,
             lambda df, c=col, k=keys: df[c].notna() & ~df[c].isin(k)))
        return self

    def dtype(self, col: str, kind: str, severity: str = CRITICAL) -> "Suite":
        """kind: 'datetime' | 'numeric' | 'integer' | 'bool' | 'string'"""
        tests = {
            "datetime": pd.api.types.is_datetime64_any_dtype,
            "numeric": pd.api.types.is_numeric_dtype,
            "integer": pd.api.types.is_integer_dtype,
            "bool": lambda s: pd.api.types.is_bool_dtype(s) or str(s.dtype) == "boolean",
            "string": lambda s: pd.api.types.is_string_dtype(s)
            or pd.api.types.is_object_dtype(s),
        }
        test = tests[kind]
        self._checks.append(
            (f"{col}: тип {kind}", severity,
             lambda df, c=col, t=test: 0 if t(df[c]) else len(df)))
        return self

    def custom(self, name: str, bad_rows: Callable[[pd.DataFrame], pd.Series],
               severity: str = CRITICAL) -> "Suite":
        """bad_rows(df) возвращает маску строк, которые нарушают правило."""
        self._checks.append((name, severity, bad_rows))
        return self

    # --- запуск -----------------------------------------------------------
    def run(self, df: pd.DataFrame) -> Report:
        rep = Report(self.table, [], len(df))
        for name, severity, fn in self._checks:
            try:
                out = fn(df)
                if isinstance(out, (int,)):
                    n_bad, detail = int(out), ""
                else:
                    mask = out.fillna(False).astype(bool)
                    n_bad = int(mask.sum())
                    detail = ""
                    if n_bad:
                        idx = df.index[mask][:3]
                        detail = f"примеры строк: {list(idx)}"
            except KeyError as exc:
                n_bad, detail = len(df), f"нет колонки {exc}"
            rep.results.append(ExpectationResult(name, severity, n_bad, len(df), detail))
        return rep


def save_reports(reports: list[Report], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "all_passed": all(r.passed for r in reports),
        "n_critical_failures": sum(len(r.critical_failed) for r in reports),
        "tables": [r.to_dict() for r in reports],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return path
