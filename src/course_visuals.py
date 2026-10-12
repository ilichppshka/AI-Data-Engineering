"""Схемы для тетрадей курса: рисуются локально в SVG, сеть не нужна."""
from __future__ import annotations

from IPython.display import SVG, display

FONT = 14           # размер подписи в блоке
CHAR = 7.9          # средняя ширина символа при этом размере
PAD = 26            # поля внутри блока
LINE = 18           # межстрочный интервал

PALETTE = {
    "src":  ("#eef4ff", "#3a6fb5"),     # источники
    "raw":  ("#fff4e3", "#c07d18"),     # сырой слой
    "ok":   ("#ecf8f1", "#26855c"),     # проверенные данные
    "bad":  ("#fdeeee", "#c0453f"),     # брак, ошибки
    "use":  ("#f3f0fb", "#6a4fb0"),     # потребители
}

_DEFS = """
<defs>
  <marker id="ar" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
    <path d="M0,0 L10,4 L0,8 Z" fill="#6b7a90"/>
  </marker>
</defs>
<style>
  .bx  { stroke-width: 1.6 }
  .lbl { font: 600 14px "Segoe UI", system-ui, sans-serif; fill: #16202e }
  .cap { font: 12px "Segoe UI", system-ui, sans-serif; fill: #55637a }
  .arw { stroke: #6b7a90; stroke-width: 1.7; fill: none; marker-end: url(#ar) }
</style>
"""


class _Canvas:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.boxes: dict[str, tuple[float, float, float, float]] = {}
        self.extent = [0.0, 0.0]            # правый и нижний край содержимого

    def box(self, key: str, x: float, y: float, text: str, kind: str = "src",
            caption: str = "") -> tuple[float, float, float, float]:
        lines = text.split("\n")
        w = max(len(s) for s in lines) * CHAR + 2 * PAD
        h = 26 + LINE * len(lines)
        fill, stroke = PALETTE[kind]
        self.parts.append(
            f'<rect class="bx" x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" '
            f'rx="9" fill="{fill}" stroke="{stroke}"/>')
        top = y + h / 2 - LINE * (len(lines) - 1) / 2 + 5
        for i, s in enumerate(lines):
            self.parts.append(
                f'<text class="lbl" x="{x + w / 2:.0f}" y="{top + i * LINE:.0f}" '
                f'text-anchor="middle">{s}</text>')
        if caption:
            self.parts.append(
                f'<text class="cap" x="{x + w / 2:.0f}" y="{y - 9:.0f}" '
                f'text-anchor="middle">{caption}</text>')
        self.boxes[key] = (x, y, w, h)
        self.extent = [max(self.extent[0], x + w), max(self.extent[1], y + h)]
        return self.boxes[key]

    def right_of(self, key: str, gap: float = 46) -> float:
        x, _, w, _ = self.boxes[key]
        return x + w + gap

    def arrow(self, a: str, b: str) -> None:
        """Стрелка от правого края одного блока к левому краю другого."""
        ax, ay, aw, ah = self.boxes[a]
        bx, by, bw, bh = self.boxes[b]
        x1, y1 = ax + aw, ay + ah / 2
        x2, y2 = bx, by + bh / 2
        if abs(y1 - y2) < 2:
            self.parts.append(f'<path class="arw" d="M{x1:.0f},{y1:.0f} L{x2 - 3:.0f},{y2:.0f}"/>')
        else:                                   # мягкий изгиб к соседнему ряду
            mid = (x1 + x2) / 2
            self.parts.append(
                f'<path class="arw" d="M{x1:.0f},{y1:.0f} C{mid:.0f},{y1:.0f} '
                f'{mid:.0f},{y2:.0f} {x2 - 3:.0f},{y2:.0f}"/>')

    def note(self, x: float, y: float, text: str, anchor: str = "start") -> None:
        self.parts.append(
            f'<text class="cap" x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}">{text}</text>')
        self.extent = [max(self.extent[0], x + len(text) * 6.4),
                       max(self.extent[1], y + 6)]

    def render(self, pad: float = 14) -> None:
        w, h = self.extent[0] + pad, self.extent[1] + pad
        display(SVG(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" '
                    f'height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}">{_DEFS}'
                    + "".join(self.parts) + "</svg>"))


def _chain(items, y: float = 40, x0: float = 14, gap: float = 46) -> _Canvas:
    c = _Canvas()
    x = x0
    prev = None
    for key, text, kind, caption in items:
        c.box(key, x, y, text, kind, caption)
        if prev:
            c.arrow(prev, key)
        prev = key
        x = c.right_of(key, gap)
    return c


def show_visual(name: str) -> None:
    if name == "course":
        c = _chain([
            ("src", "Источники\n9 файлов", "src", ""),
            ("raw", "Сырой слой\nкак прислали", "raw", "ЛР 1–2"),
            ("cln", "Проверенный\nслой", "ok", "ЛР 3"),
            ("core", "Модель данных\nфакты и справочники", "ok", "ЛР 4"),
            ("mart", "Витрины", "use", "ЛР 4"),
        ])
        x = c.right_of("mart", 52)
        c.box("bi", x, 8, "Отчёты", "use")
        c.box("ml", x, 78, "Модель", "use", "")
        c.arrow("mart", "bi")
        c.arrow("mart", "ml")
        c.note(14, 156, "ЛР 5: расписание, повторные запуски, восстановление истории")
        c.note(14, 174, "ЛР 6: рост объёмов, поток событий, признаки для обучения")
        c.render()

    elif name == "flow":
        c = _chain([
            ("f", "9 файлов CSV\nвыгрузка из магазина", "src", "источник"),
            ("r", "Читаем\nничего не меняя", "raw", "приём"),
            ("t", "Считаем\nпо дням", "ok", "преобразование"),
            ("m", "Витрина\nзаказы по дням", "use", "результат"),
        ])
        c.note(14, 150, "Один заказ должен остаться одним заказом на всём пути.")
        c.render()

    elif name == "olist":
        c = _Canvas()
        c.box("cu", 14, 108, "customers\n1 строка = покупатель", "src")
        c.box("or", 268, 108, "orders\n1 строка = заказ", "src")
        c.box("it", 546, 14, "order_items\n1 строка = позиция", "raw")
        c.box("pa", 546, 108, "payments\n1 строка = платёж", "raw")
        c.box("re", 546, 202, "reviews\n1 строка = отзыв", "raw")
        c.arrow("cu", "or")
        for t in ("it", "pa", "re"):
            c.arrow("or", t)
        c.note(14, 288, "Справа от заказа строк больше, чем заказов. Соединив такие "
                        "таблицы напрямую, мы размножим заказы.")
        c.render()

    elif name == "join":
        c = _Canvas()
        c.box("o", 14, 14, "orders\n1 строка = заказ", "src")
        c.box("p", 14, 104, "payments\n1 строка = платёж", "raw")
        c.box("j", 260, 60, "соединение\nпо order_id", "bad")
        c.box("res", 470, 60, "103 886 строк\nвместо 99 441 заказа", "bad")
        c.arrow("o", "j")
        c.arrow("p", "j")
        c.arrow("j", "res")
        c.note(14, 196, "Лечение: сначала свернуть платежи до одного на заказ, потом соединять.")
        c.render()

    elif name == "storage":
        c = _Canvas()
        c.box("r1", 14, 42, "заказ 1: дата, клиент, сумма, статус", "src")
        c.box("r2", 14, 96, "заказ 2: дата, клиент, сумма, статус", "src")
        c.box("r3", 14, 150, "заказ 3: дата, клиент, сумма, статус", "src")
        c.note(14, 30, "Строковое хранение: рядом лежит вся строка")

        c.box("c1", 470, 42, "все даты", "ok")
        c.box("c2", 470, 96, "все клиенты", "ok")
        c.box("c3", 470, 150, "все суммы", "ok")
        c.note(470, 30, "Колоночное: рядом лежит вся колонка")
        c.note(14, 220, "Карточку одного заказа быстрее читать слева. Сумму по всем "
                        "заказам – справа: читается один кусок файла.")
        c.render()

    elif name == "quality":
        c = _Canvas()
        c.box("raw", 14, 60, "Сырой слой", "raw")
        c.box("chk", 200, 60, "Схема\nи правила", "src")
        c.box("cl", 420, 12, "Проверенный слой", "ok")
        c.box("q", 420, 108, "Карантин\nи причина брака", "bad")
        c.arrow("raw", "chk")
        c.arrow("chk", "cl")
        c.arrow("chk", "q")
        c.note(14, 196, "Строку, не прошедшую правило, не удаляют молча – её откладывают.")
        c.render()

    elif name == "star":
        c = _Canvas()
        c.box("f", 300, 70, "fact_order_items\n1 строка = позиция заказа", "raw")
        c.box("d1", 20, 10, "dim_date", "src")
        c.box("d2", 20, 130, "dim_customer", "src")
        c.box("d3", 640, 10, "dim_product", "src")
        c.box("d4", 640, 130, "dim_seller", "src")
        c.arrow("d1", "f")
        c.arrow("d2", "f")
        for a in ("d3", "d4"):
            ax, ay, aw, ah = c.boxes[a]
            fx, fy, fw, fh = c.boxes["f"]
            c.parts.append(f'<path class="arw" d="M{ax:.0f},{ay + ah / 2:.0f} '
                           f'C{ax - 60:.0f},{ay + ah / 2:.0f} {fx + fw + 60:.0f},'
                           f'{fy + fh / 2:.0f} {fx + fw + 3:.0f},{fy + fh / 2:.0f}"/>')
        c.render()

    elif name == "dag":
        c = _chain([
            ("i", "приём", "src", ""),
            ("v", "проверка\nкачества", "ok", ""),
            ("t", "преобразование", "ok", ""),
            ("m", "витрина", "use", ""),
            ("c", "контроль\nрезультата", "src", ""),
        ])
        c.note(14, 150, "Упала проверка – витрину не трогаем: лучше вчерашние данные, чем половина сегодняшних.")
        c.note(14, 168, "Повторный запуск за тот же период обязан дать тот же результат.")
        c.render()

    elif name == "spark":
        c = _Canvas()
        c.box("d", 14, 92, "Управляющий процесс\nделит работу и собирает ответ", "src")
        c.box("e1", 330, 14, "Исполнитель 1\nчасть данных", "ok")
        c.box("e2", 330, 92, "Исполнитель 2\nчасть данных", "ok")
        c.box("e3", 330, 170, "Исполнитель 3\nчасть данных", "ok")
        c.box("r", 620, 92, "Итог", "use")
        for e in ("e1", "e2", "e3"):
            c.arrow("d", e)
            c.arrow(e, "r")
        c.note(14, 258, "Пересылка данных между исполнителями – самая дорогая часть; "
                        "её стараются избегать.")
        c.render()

    elif name == "features":
        c = _chain([
            ("core", "Модель данных\nфакты и справочники", "ok", ""),
            ("f", "Таблица признаков\nстрока = заказ", "use", ""),
            ("split", "Разделение\nпо времени", "src", ""),
            ("m", "Обучение\nи проверка", "use", ""),
        ])
        c.note(14, 150, "В признаки попадает только то, что было известно в момент заказа.")
        c.note(14, 168, "Дата доставки известна позже – в признаках ей не место.")
        c.render()

    elif name == "stream":
        c = _Canvas()
        c.box("p", 14, 70, "Источник\nсобытий", "src")
        c.box("t", 210, 70, "Журнал событий\nсобытия не удаляются", "raw")
        c.box("c1", 480, 14, "Антифрод\nчитает сразу", "bad")
        c.box("c2", 480, 126, "Аналитика\nчитает пачкой", "ok")
        c.arrow("p", "t")
        c.arrow("t", "c1")
        c.arrow("t", "c2")
        c.note(14, 212, "Каждый потребитель держит свою позицию в журнале и читает со своей скоростью.")
        c.render()

    else:
        raise ValueError(f"Неизвестная схема: {name}")


# Официальные схемы из документации Apache. Лежат локально, чтобы тетрадь
# не зависела от сети; условия использования – в assets/external/ATTRIBUTION.md.

EXTERNAL = {
    "parquet_layout": {
        "file": "parquet/parquet_file_layout.gif",
        "width": 560,
        "alt": "Устройство файла Parquet: row groups, колонки внутри них, страницы и footer с метаданными",
        "source": "Apache Parquet Documentation",
        "url": "https://parquet.apache.org/docs/file-format/",
    },
    "iceberg_metadata": {
        "file": "iceberg/iceberg_table_metadata.png",
        "width": 560,
        "alt": "Таблица Iceberg: слой данных из файлов и слой метаданных со снимками и манифестами",
        "source": "Apache Iceberg Documentation",
        "url": "https://iceberg.apache.org/spec/",
    },
    "airflow_architecture": {
        "file": "airflow/airflow_architecture.png",
        "width": 720,
        "alt": "Устройство Airflow: папка с файлами DAG, планировщик, веб-интерфейс и база метаданных",
        "source": "Apache Airflow Documentation",
        "url": "https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/overview.html",
    },
    "spark_cluster": {
        "file": "spark/spark_cluster_overview.png",
        "width": 620,
        "alt": "Driver Program, Cluster Manager и Worker Nodes с executors и задачами",
        "source": "Apache Spark Documentation",
        "url": "https://spark.apache.org/docs/latest/cluster-overview.html",
    },
    "kafka_consumer_groups": {
        "file": "kafka/kafka_consumer_groups.png",
        "width": 520,
        "alt": "Разделы топика Kafka, распределённые между потребителями двух групп",
        "source": "Apache Kafka Documentation",
        "url": "https://kafka.apache.org/intro",
    },
}


def show_external_visual(name: str, caption: str = "") -> None:
    """Показать официальную схему. Картинка встраивается в вывод ячейки,
    поэтому видна везде одинаково и не требует сети."""
    import base64
    import mimetypes
    from pathlib import Path

    from IPython.display import HTML, display

    import paths

    meta = EXTERNAL[name]
    path = Path(paths.ROOT) / "assets" / "external" / meta["file"]
    if not path.exists():
        raise FileNotFoundError(f"нет файла схемы: {path}")

    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    text = f"{caption}<br>" if caption else ""
    display(HTML(
        f'<figure style="margin:8px 0 14px">'
        f'<img src="data:{mime};base64,{data}" width="{meta["width"]}" '
        f'alt="{meta["alt"]}" style="max-width:100%">'
        f'<figcaption style="font:12px sans-serif;color:#55637a;margin-top:6px">'
        f'<b>Рисунок.</b> {text}'
        f'Источник: <a href="{meta["url"]}">{meta["source"]}</a>, лицензия Apache 2.0.'
        f'</figcaption></figure>'))
