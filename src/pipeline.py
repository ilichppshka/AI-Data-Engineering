"""Мини-оркестратор: зависимости между задачами, повторы, журнал запусков.

Порядок выполнения считается топологической сортировкой, циклы и ссылки на
несуществующие задачи ловятся до старта. Упавшая задача останавливает тех,
кто от неё зависит.

Планировщика, веб-интерфейса и распределённого выполнения здесь нет –
за ними в пятой работе идём к Airflow.
"""
from __future__ import annotations

import json
import logging
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

SUCCESS = "success"
FAILED = "failed"
SKIPPED = "upstream_failed"
PENDING = "pending"


class CyclicDependencyError(RuntimeError):
    pass


@dataclass
class Task:
    name: str
    fn: Callable[[dict], Any]
    depends_on: list[str] = field(default_factory=list)
    retries: int = 0
    retry_delay: float = 0.0


@dataclass
class TaskRun:
    name: str
    status: str = PENDING
    attempts: int = 0
    seconds: float = 0.0
    error: str = ""
    result: Any = None


@dataclass
class RunResult:
    pipeline: str
    run_id: str
    status: str
    tasks: dict[str, TaskRun]
    started_at: str
    seconds: float
    context: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == SUCCESS

    @property
    def order(self) -> list[str]:
        """Порядок, в котором задачи реально выполнялись."""
        return [n for n, t in self.tasks.items() if t.status != PENDING]

    def show(self) -> "RunResult":
        mark = {SUCCESS: "✓", FAILED: "✗", SKIPPED: "·", PENDING: " "}
        print(f"\nЗапуск {self.pipeline} [{self.run_id}] → {self.status.upper()}"
              f"  ({self.seconds:.2f} c)")
        print("-" * 66)
        for name, t in self.tasks.items():
            line = f" {mark[t.status]} {name:<22} {t.status:<16} {t.seconds:6.2f} c"
            if t.attempts > 1:
                line += f"  попыток: {t.attempts}"
            print(line)
            if t.error:
                print(f"     → {t.error.splitlines()[-1][:110]}")
        print("-" * 66)
        return self

    def to_dict(self) -> dict:
        return {
            "pipeline": self.pipeline, "run_id": self.run_id,
            "status": self.status, "started_at": self.started_at,
            "seconds": round(self.seconds, 3),
            "tasks": {n: {"status": t.status, "attempts": t.attempts,
                          "seconds": round(t.seconds, 3), "error": t.error}
                      for n, t in self.tasks.items()},
        }


class Pipeline:
    def __init__(self, name: str, tasks: list[Task],
                 log_dir: str | Path | None = None,
                 runs_dir: str | Path | None = None):
        self.name = name
        self.tasks = {t.name: t for t in tasks}
        if len(self.tasks) != len(tasks):
            raise ValueError("имена задач должны быть уникальными")
        self.log_dir = Path(log_dir) if log_dir else None
        self.runs_dir = Path(runs_dir) if runs_dir else None
        self._logger = self._make_logger()

    # ------------------------------------------------------------------ DAG
    def order(self) -> list[str]:
        """Топологическая сортировка: кто от кого зависит."""
        for t in self.tasks.values():
            for dep in t.depends_on:
                if dep not in self.tasks:
                    raise ValueError(
                        f"задача '{t.name}' зависит от неизвестной задачи '{dep}'")
        pending = {n: list(t.depends_on) for n, t in self.tasks.items()}
        done, out = set(), []
        while pending:
            ready = sorted(n for n, deps in pending.items()
                           if all(d in done for d in deps))
            if not ready:
                raise CyclicDependencyError(
                    f"в DAG есть цикл среди задач: {sorted(pending)}")
            for n in ready:
                out.append(n)
                done.add(n)
                pending.pop(n)
        return out

    def draw(self) -> str:
        lines = [f"DAG '{self.name}':"]
        for n in self.order():
            deps = self.tasks[n].depends_on
            lines.append(f"  {n:<22} ← {', '.join(deps) if deps else '(нет зависимостей)'}")
        return "\n".join(lines)

    # -------------------------------------------------------------- запуск
    def run(self, context: dict | None = None,
            only: list[str] | None = None) -> RunResult:
        ctx = dict(context or {})
        run_id = datetime.now().strftime("%Y%m%dT%H%M%S")
        started = datetime.now()
        runs = {n: TaskRun(n) for n in self.tasks}
        order = [n for n in self.order() if only is None or n in only]

        self._logger.info("=== запуск %s [%s] ===", self.name, run_id)
        t_all = time.perf_counter()
        for name in order:
            task = self.tasks[name]
            failed_deps = [d for d in task.depends_on
                           if runs[d].status in (FAILED, SKIPPED)]
            if failed_deps:
                runs[name].status = SKIPPED
                self._logger.warning("· %s пропущена: упала зависимость %s",
                                     name, failed_deps)
                continue

            t0 = time.perf_counter()
            for attempt in range(1, task.retries + 2):
                runs[name].attempts = attempt
                try:
                    self._logger.info("→ %s (попытка %d)", name, attempt)
                    runs[name].result = task.fn(ctx)
                    runs[name].status = SUCCESS
                    runs[name].error = ""
                    self._logger.info("✓ %s за %.2f c", name,
                                      time.perf_counter() - t0)
                    break
                except Exception as exc:                      # noqa: BLE001
                    runs[name].error = f"{type(exc).__name__}: {exc}"
                    self._logger.error("✗ %s: %s", name, runs[name].error)
                    self._logger.debug(traceback.format_exc())
                    if attempt <= task.retries:
                        time.sleep(task.retry_delay)
                    else:
                        runs[name].status = FAILED
            runs[name].seconds = time.perf_counter() - t0

        status = FAILED if any(r.status in (FAILED, SKIPPED)
                               for r in runs.values()) else SUCCESS
        result = RunResult(self.name, run_id, status, runs,
                           started.isoformat(timespec="seconds"),
                           time.perf_counter() - t_all, ctx)
        self._logger.info("=== итог %s [%s]: %s ===", self.name, run_id, status)
        self._save(result)
        return result

    def quiet(self, on: bool = True) -> "Pipeline":
        """Приглушить консольный лог (файл-лог продолжает писаться)."""
        for h in self._logger.handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(
                    h, logging.FileHandler):
                h.setLevel(logging.WARNING if on else logging.INFO)
        return self

    # ------------------------------------------------------------ служебное
    def _make_logger(self) -> logging.Logger:
        logger = logging.getLogger(f"pipeline.{self.name}")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        logger.propagate = False
        fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s",
                                "%H:%M:%S")
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(sh)
        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(self.log_dir / f"{self.name}.log",
                                     encoding="utf-8")
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        return logger

    def _save(self, result: RunResult) -> None:
        if not self.runs_dir:
            return
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        path = self.runs_dir / f"{self.name}_{result.run_id}.json"
        path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=1),
                        encoding="utf-8")
        latest = self.runs_dir / f"{self.name}_latest.json"
        latest.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=1),
                          encoding="utf-8")


def last_run(runs_dir: str | Path, pipeline: str) -> dict | None:
    p = Path(runs_dir) / f"{pipeline}_latest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
