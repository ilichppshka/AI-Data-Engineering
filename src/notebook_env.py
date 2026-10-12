"""Настройка окружения тетради.

Модуль находит папку курса, при необходимости доставляет недостающие пакеты
в текущее ядро и сообщает, какой набор данных используется. Логики
лабораторных здесь нет.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


CORE_PACKAGES = {
    "pandas": "pandas>=2.1",
    "numpy": "numpy>=1.26",
    "pyarrow": "pyarrow>=14.0",
    "duckdb": "duckdb>=0.10",
    "sklearn": "scikit-learn>=1.3",
}


def in_colab() -> bool:
    # find_spec бросает исключение, если нет самого пакета google, а не только
    # подпакета colab, – именно так выглядит обычное окружение студента.
    try:
        return importlib.util.find_spec("google.colab") is not None
    except ModuleNotFoundError:
        return False


def install_missing_core() -> list[str]:
    """Доставляет недостающие пакеты. Локально обычно не делает ничего:
    зависимости уже стоят. Нужна в основном для Colab."""
    missing = [requirement for module, requirement in CORE_PACKAGES.items()
               if importlib.util.find_spec(module) is None]
    if not missing:
        return []
    print("Устанавливаю отсутствующие пакеты для текущего kernel:", ", ".join(missing))
    try:
        from IPython import get_ipython
        ip = get_ipython()
    except ImportError:
        ip = None
    if ip is not None:
        ip.run_line_magic("pip", "install -q " + " ".join(missing))
    else:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *missing])
    return missing


def install_colab_data_loader() -> bool:
    """В Colab добавляет лёгкий клиент Kaggle, если его ещё нет.

    Это не часть обязательного локального окружения: локально всегда можно
    положить ZIP рядом с проектом. В Colab пакет нужен для первой попытки
    получить публичный Olist без ручной загрузки.
    """
    if not in_colab() or importlib.util.find_spec("kagglehub") is not None:
        return False
    print("Добавляю kagglehub для загрузки публичного Olist…")
    try:
        from IPython import get_ipython
        ip = get_ipython()
    except ImportError:
        ip = None
    if ip is not None:
        ip.run_line_magic("pip", "install -q kagglehub>=0.3")
    else:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "kagglehub>=0.3"])
    return True


def data_mode() -> str:
    """Режим данных: auto (полный Olist), local, kaggle или synthetic.

    Synthetic выбирается только явно через COURSE_DATA_MODE=synthetic, чтобы
    студент не принял учебный sample за настоящий Olist.
    """
    return os.environ.get("COURSE_DATA_MODE", "auto").strip().lower()


def describe_data_source(source: str) -> None:
    if source.startswith("synthetic"):
        print("\n⚠ Используется учебный synthetic sample, а не полный Olist. "
              "Для полного набора скачайте Olist или уберите COURSE_DATA_MODE=synthetic.")


def setup_course(root) -> "Path":
    """Рабочая папка, пути, недостающие пакеты – всё, что нужно тетради."""
    import os
    root = Path(root)
    os.chdir(root)
    for p in (str(root), str(root / "src")):
        if p not in sys.path:
            sys.path.insert(0, p)
    install_missing_core()
    install_colab_data_loader()
    import paths
    paths.ensure_dirs()
    return root
