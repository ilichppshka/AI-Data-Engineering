"""Получение датасета курса.

Пробуем по порядку: Kaggle через kagglehub, локальный архив в data/raw,
офлайн-генератор той же схемы. Проверки курса написаны по инвариантам
результата, поэтому работают с любым из вариантов.
"""
from __future__ import annotations

import shutil
import os
import zipfile
from pathlib import Path

from paths import RAW, RAW_OLIST, ensure_dirs

KAGGLE_SLUG = "olistbr/brazilian-ecommerce"

EXPECTED = [
    "olist_customers_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "product_category_name_translation.csv",
]


def _complete(d: Path) -> bool:
    return d.exists() and all((d / f).exists() for f in EXPECTED)


def _from_kaggle() -> bool:
    try:
        import kagglehub
    except ImportError:
        return False
    try:
        path = Path(kagglehub.dataset_download(KAGGLE_SLUG))
    except Exception as exc:                       # нет сети / нет токена / 403
        print(f"   kagglehub недоступен: {type(exc).__name__}: {exc}")
        return False
    for f in EXPECTED:
        src = next(path.rglob(f), None)
        if src is None:
            print(f"   в скачанном датасете нет {f}")
            return False
        shutil.copy(src, RAW_OLIST / f)
    (RAW_OLIST / "_SOURCE.txt").write_text(f"kaggle:{KAGGLE_SLUG}\n", encoding="utf-8")
    return True


def _from_local_archive() -> bool:
    """Ищем скачанный руками ZIP или распакованную папку в data/raw/."""
    for z in RAW.glob("*.zip"):
        with zipfile.ZipFile(z) as zf:
            names = {Path(n).name for n in zf.namelist()}
            if not set(EXPECTED) <= names:
                continue
            for n in zf.namelist():
                if Path(n).name in EXPECTED:
                    with zf.open(n) as fsrc, open(RAW_OLIST / Path(n).name, "wb") as fdst:
                        shutil.copyfileobj(fsrc, fdst)
        (RAW_OLIST / "_SOURCE.txt").write_text(f"local-zip:{z.name}\n", encoding="utf-8")
        return True
    for d in RAW.iterdir() if RAW.exists() else []:
        if d.is_dir() and d != RAW_OLIST and _complete(d):
            for f in EXPECTED:
                shutil.copy(d / f, RAW_OLIST / f)
            (RAW_OLIST / "_SOURCE.txt").write_text(f"local-dir:{d.name}\n", encoding="utf-8")
            return True
    return False


def source_kind() -> str:
    p = RAW_OLIST / "_SOURCE.txt"
    return p.read_text(encoding="utf-8").splitlines()[0] if p.exists() else "unknown"


def get_olist(prefer: str | None = None, force: bool = False, quiet: bool = False) -> Path:
    """
    prefer: 'auto' | 'kaggle' | 'local' | 'synthetic'; если не указан,
    берётся COURSE_DATA_MODE (по умолчанию auto).
    Возвращает папку с CSV (data/raw/olist).

    ``auto`` никогда не подменяет полный Olist учебным sample молча. Если
    Kaggle и локальный архив недоступны, студент получает короткую инструкцию
    выбрать ``synthetic`` явно. Это важно для честной интерпретации результатов.
    """
    ensure_dirs()
    prefer = prefer or os.environ.get("COURSE_DATA_MODE", "auto").strip().lower()
    if _complete(RAW_OLIST) and not force:
        if not quiet:
            print(f"✓ данные уже на месте: {RAW_OLIST}  (источник: {source_kind()})")
        return RAW_OLIST

    if prefer not in {"auto", "kaggle", "local", "synthetic"}:
        raise ValueError("prefer должен быть auto, kaggle, local или synthetic")

    order = {"auto": ["kaggle", "local"],
             "kaggle": ["kaggle"], "local": ["local"],
             "synthetic": ["synthetic"]}[prefer]

    for step in order:
        if step == "kaggle":
            print("→ пробуем скачать с Kaggle (kagglehub)…")
            if _from_kaggle():
                print(f"✓ данные с Kaggle: {RAW_OLIST}")
                return RAW_OLIST
        elif step == "local":
            print("→ ищем локальный архив в data/raw/…")
            if _from_local_archive():
                print(f"✓ данные из локального архива: {RAW_OLIST}")
                return RAW_OLIST
        else:
            print("→ Kaggle недоступен, генерируем офлайн-датасет той же схемы…")
            from synth_olist import generate
            generate(RAW_OLIST)
            print(f"✓ офлайн-датасет готов: {RAW_OLIST}")
            return RAW_OLIST

    raise RuntimeError(
        "Полный Olist не найден. Скачайте ZIP из Kaggle в data/raw/ или "
        "явно включите учебный набор: COURSE_DATA_MODE=synthetic. "
        "Скачайте датасет вручную и положите ZIP в data/raw."
    )


def make_sample(n_orders: int = 300) -> Path:
    """Маленький срез для технических тестов (data/sample/)."""
    import pandas as pd
    from paths import DATA
    out = DATA / "sample"
    out.mkdir(parents=True, exist_ok=True)
    orders = pd.read_csv(RAW_OLIST / "olist_orders_dataset.csv").head(n_orders)
    oid = set(orders["order_id"])
    cid = set(orders["customer_id"])
    frames = {
        "olist_orders_dataset.csv": orders,
        "olist_order_items_dataset.csv": None,
        "olist_order_payments_dataset.csv": None,
        "olist_order_reviews_dataset.csv": None,
        "olist_customers_dataset.csv": None,
    }
    for f in list(frames):
        if frames[f] is None:
            df = pd.read_csv(RAW_OLIST / f)
            key = "customer_id" if "customers" in f else "order_id"
            frames[f] = df[df[key].isin(cid if key == "customer_id" else oid)]
    items = frames["olist_order_items_dataset.csv"]
    prods = pd.read_csv(RAW_OLIST / "olist_products_dataset.csv")
    sell = pd.read_csv(RAW_OLIST / "olist_sellers_dataset.csv")
    frames["olist_products_dataset.csv"] = prods[prods["product_id"].isin(items["product_id"])]
    frames["olist_sellers_dataset.csv"] = sell[sell["seller_id"].isin(items["seller_id"])]
    frames["product_category_name_translation.csv"] = pd.read_csv(
        RAW_OLIST / "product_category_name_translation.csv")
    for f, df in frames.items():
        df.to_csv(out / f, index=False)
    return out


if __name__ == "__main__":
    import sys
    prefer = sys.argv[1] if len(sys.argv) > 1 else "auto"
    get_olist(prefer=prefer)
