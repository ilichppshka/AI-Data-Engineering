"""Брокер событий в памяти – учебная модель Kafka.

Топик здесь – журнал записей со смещениями: producer дописывает в конец,
consumer читает с того места, где остановился, и сам фиксирует смещение.
Если он упал до фиксации, те же записи придут повторно – отсюда дубликаты,
с которыми разбирается шестая работа.

Сети, репликации и ребаланса групп здесь нет.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator


@dataclass
class Record:
    offset: int
    key: str | None
    value: dict
    ts: str


class Topic:
    """Упорядоченный журнал записей."""

    def __init__(self, name: str):
        self.name = name
        self._log: list[Record] = []

    def produce(self, value: dict, key: str | None = None) -> int:
        rec = Record(len(self._log), key, value,
                     datetime.now().isoformat(timespec="seconds"))
        self._log.append(rec)
        return rec.offset

    def read(self, offset: int = 0, limit: int | None = None) -> list[Record]:
        chunk = self._log[offset:]
        return chunk if limit is None else chunk[:limit]

    def __len__(self) -> int:
        return len(self._log)

    def __iter__(self) -> Iterator[Record]:
        return iter(self._log)


class Consumer:
    """Потребитель с собственным смещением и ручным коммитом."""

    def __init__(self, topic: Topic, group: str = "default"):
        self.topic = topic
        self.group = group
        self.committed = 0          # зафиксированное смещение
        self.position = 0           # где мы сейчас читаем

    def poll(self, max_records: int = 100) -> list[Record]:
        batch = self.topic.read(self.position, max_records)
        self.position += len(batch)
        return batch

    def commit(self) -> int:
        self.committed = self.position
        return self.committed

    def crash(self) -> int:
        """Падение до коммита: при следующем чтении записи придут снова."""
        self.position = self.committed
        return self.position

    def seek(self, offset: int) -> int:
        self.position = offset
        return offset


def produce_events(topic: Topic, events: list[dict],
                   duplicate_rate: float = 0.0, seed: int = 7) -> int:
    """Отправляет события; часть – дважды (имитация at-least-once у источника)."""
    rng = random.Random(seed)
    n = 0
    for e in events:
        topic.produce(e, key=str(e.get("order_id")))
        n += 1
        if duplicate_rate and rng.random() < duplicate_rate:
            topic.produce(dict(e), key=str(e.get("order_id")))
            n += 1
    return n
