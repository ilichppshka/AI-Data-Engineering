"""Офлайн-версия датасета Olist.

Те же имена файлов и колонок, те же связи и те же классы дефектов, что
в оригинале с Kaggle. Нужна, когда на занятии нет интернета. Данные
детерминированы, поэтому у всех получаются одинаковые числа.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

CATEGORIES = [
    ("cama_mesa_banho", "bed_bath_table"), ("beleza_saude", "health_beauty"),
    ("esporte_lazer", "sports_leisure"), ("informatica_acessorios", "computers_accessories"),
    ("moveis_decoracao", "furniture_decor"), ("utilidades_domesticas", "housewares"),
    ("relogios_presentes", "watches_gifts"), ("telefonia", "telephony"),
    ("automotivo", "auto"), ("brinquedos", "toys"),
    ("cool_stuff", "cool_stuff"), ("ferramentas_jardim", "garden_tools"),
    ("perfumaria", "perfumery"), ("bebes", "baby"), ("eletronicos", "electronics"),
    ("papelaria", "stationery"), ("fashion_bolsas_e_acessorios", "fashion_bags_accessories"),
    ("pet_shop", "pet_shop"), ("moveis_escritorio", "office_furniture"),
    ("construcao_ferramentas_construcao", "construction_tools_construction"),
]

STATES = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "GO", "ES", "PE", "CE"]
STATE_W = np.array([42, 13, 12, 5.5, 5, 3.5, 3.4, 2.4, 2.2, 2.1, 1.7, 1.2])
CITIES = {
    "SP": ["sao paulo", "campinas", "guarulhos", "santos", "sorocaba"],
    "RJ": ["rio de janeiro", "niteroi", "duque de caxias", "campos"],
    "MG": ["belo horizonte", "uberlandia", "contagem", "juiz de fora"],
    "RS": ["porto alegre", "caxias do sul", "pelotas"],
    "PR": ["curitiba", "londrina", "maringa"],
    "SC": ["florianopolis", "joinville", "blumenau"],
    "BA": ["salvador", "feira de santana"], "DF": ["brasilia"],
    "GO": ["goiania", "aparecida de goiania"], "ES": ["vitoria", "vila velha"],
    "PE": ["recife", "jaboatao"], "CE": ["fortaleza"],
}
PAYMENT_TYPES = ["credit_card", "boleto", "voucher", "debit_card"]


def _ids(rng: np.random.Generator, n: int, prefix: str = "") -> np.ndarray:
    """32-символьные hex-идентификаторы, как в оригинальном датасете."""
    raw = rng.integers(0, 16, size=(n, 32))
    hexmap = np.array(list("0123456789abcdef"))
    out = np.array(["".join(r) for r in hexmap[raw]])
    if prefix:
        out = np.char.add(prefix, out)
    return out


def _fmt(ts: pd.Series) -> pd.Series:
    return ts.dt.strftime("%Y-%m-%d %H:%M:%S")


def generate(out_dir: str | Path, n_orders: int = 8000, seed: int = 42) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------ sellers
    n_sellers = 300
    s_state = rng.choice(STATES, n_sellers, p=STATE_W / STATE_W.sum())
    sellers = pd.DataFrame({
        "seller_id": _ids(rng, n_sellers),
        "seller_zip_code_prefix": rng.integers(1000, 99000, n_sellers),
        "seller_city": [rng.choice(CITIES[s]) for s in s_state],
        "seller_state": s_state,
    })

    # ----------------------------------------------------------------- products
    n_products = 1200
    cat = rng.choice([c[0] for c in CATEGORIES], n_products)
    products = pd.DataFrame({
        "product_id": _ids(rng, n_products),
        "product_category_name": cat,
        "product_name_lenght": rng.integers(20, 70, n_products),
        "product_description_lenght": rng.integers(100, 3000, n_products),
        "product_photos_qty": rng.integers(1, 7, n_products),
        "product_weight_g": (rng.lognormal(6.4, 1.1, n_products)).round(0),
        "product_length_cm": rng.integers(8, 90, n_products),
        "product_height_cm": rng.integers(2, 60, n_products),
        "product_width_cm": rng.integers(6, 70, n_products),
    })
    base_price = np.round(rng.lognormal(4.2, 0.8, n_products), 2)

    # ---------------------------------------------------------------- customers
    n_cust = n_orders
    c_state = rng.choice(STATES, n_cust, p=STATE_W / STATE_W.sum())
    pool = _ids(rng, int(n_orders * 0.82))          # реальные люди
    customers = pd.DataFrame({
        "customer_id": _ids(rng, n_cust),           # в Olist это ключ "заказа-клиента"
        "customer_unique_id": rng.choice(pool, n_cust),
        "customer_zip_code_prefix": rng.integers(1000, 99000, n_cust),
        "customer_city": [rng.choice(CITIES[s]) for s in c_state],
        "customer_state": c_state,
    })

    # ------------------------------------------------------------------- orders
    start = pd.Timestamp("2017-01-01")
    # ~20 месяцев, с ростом числа заказов к концу периода
    day = np.sort((rng.beta(1.7, 1.15, n_orders) * 607).astype(int))
    purchase = start + pd.to_timedelta(day, unit="D") \
        + pd.to_timedelta(rng.integers(0, 24 * 3600, n_orders), unit="s")

    status = rng.choice(
        ["delivered", "shipped", "canceled", "invoiced", "processing", "unavailable"],
        n_orders, p=[0.915, 0.03, 0.025, 0.012, 0.012, 0.006])

    approved = purchase + pd.to_timedelta(rng.exponential(0.5, n_orders) * 86400, unit="s")
    est_days = rng.integers(8, 35, n_orders)
    estimated = (purchase.normalize() + pd.to_timedelta(est_days, unit="D")
                 + pd.Timedelta(hours=12))

    orders = pd.DataFrame({
        "order_id": _ids(rng, n_orders),
        "customer_id": customers["customer_id"].to_numpy(),
        "order_status": status,
        "order_purchase_timestamp": purchase,
        "order_approved_at": approved,
        "order_estimated_delivery_date": estimated,
    })

    # -------------------------------------------------------------- order_items
    n_items = 1 + rng.geometric(0.83, n_orders) - 1
    n_items = np.clip(n_items, 1, 6)
    oi_order = np.repeat(orders["order_id"].to_numpy(), n_items)
    oi_seq = np.concatenate([np.arange(1, k + 1) for k in n_items])
    total_items = len(oi_order)
    prod_idx = rng.integers(0, n_products, total_items)
    seller_idx = rng.integers(0, n_sellers, total_items)
    price = np.round(base_price[prod_idx] * rng.normal(1.0, 0.07, total_items), 2)
    price = np.clip(price, 1.2, None)

    oi_purchase = np.repeat(purchase.to_numpy(), n_items)
    cust_state_rep = np.repeat(c_state, n_items)
    sell_state_rep = sellers["seller_state"].to_numpy()[seller_idx]
    cross_state = (cust_state_rep != sell_state_rep)
    weight = products["product_weight_g"].to_numpy()[prod_idx]
    freight = np.round(7.5 + 0.004 * weight + 9.0 * cross_state
                       + rng.normal(0, 2.0, total_items), 2)
    freight = np.clip(freight, 0.0, None)

    order_items = pd.DataFrame({
        "order_id": oi_order,
        "order_item_id": oi_seq,
        "product_id": products["product_id"].to_numpy()[prod_idx],
        "seller_id": sellers["seller_id"].to_numpy()[seller_idx],
        "shipping_limit_date": pd.to_datetime(oi_purchase)
        + pd.to_timedelta(rng.integers(2, 9, total_items), unit="D"),
        "price": price,
        "freight_value": freight,
    })

    # --------------------------------------------------- доставка (для таргета)
    per_order = pd.DataFrame({
        "order_id": oi_order, "cross": cross_state, "freight": freight,
    }).groupby("order_id", as_index=False).agg(
        cross=("cross", "max"), freight=("freight", "sum"), n_items=("cross", "size"))
    per_order = orders[["order_id"]].merge(per_order, on="order_id", how="left")

    month = purchase.month.to_numpy()
    late_logit = (-1.55
                  + 0.85 * per_order["cross"].to_numpy().astype(float)
                  + 0.11 * per_order["n_items"].to_numpy()
                  + 0.010 * per_order["freight"].to_numpy()
                  + 0.55 * np.isin(month, [11, 12]).astype(float)
                  - 0.035 * est_days)
    p_late = 1 / (1 + np.exp(-late_logit))
    is_late = rng.random(n_orders) < p_late

    transit = np.where(
        is_late,
        est_days + rng.integers(1, 22, n_orders),
        np.maximum(1, est_days - rng.integers(1, 14, n_orders)))
    delivered_cust = purchase.normalize() + pd.to_timedelta(transit, unit="D") \
        + pd.to_timedelta(rng.integers(0, 24 * 3600, n_orders), unit="s")
    delivered_carrier = purchase + pd.to_timedelta(
        rng.integers(1, 5, n_orders), unit="D")

    orders["order_delivered_carrier_date"] = delivered_carrier
    orders["order_delivered_customer_date"] = delivered_cust
    not_delivered = orders["order_status"].to_numpy() != "delivered"
    orders.loc[not_delivered, "order_delivered_customer_date"] = pd.NaT
    orders.loc[np.isin(orders["order_status"], ["canceled", "unavailable",
                                                "processing", "invoiced"]),
               "order_delivered_carrier_date"] = pd.NaT

    # ----------------------------------------------------------------- payments
    order_total = (order_items.groupby("order_id")[["price", "freight_value"]]
                   .sum().sum(axis=1).round(2))
    order_total = order_total.reindex(orders["order_id"]).fillna(0.0)
    n_pay = np.where(rng.random(n_orders) < 0.14, 2, 1)
    n_pay = np.where(rng.random(n_orders) < 0.03, 3, n_pay)
    pay_rows = []
    totals = order_total.to_numpy()
    oids = orders["order_id"].to_numpy()
    ptype_main = rng.choice(PAYMENT_TYPES, n_orders, p=[0.74, 0.19, 0.05, 0.02])
    inst = np.where(ptype_main == "credit_card",
                    rng.choice([1, 2, 3, 4, 6, 8, 10, 12], n_orders,
                               p=[.45, .13, .12, .08, .09, .05, .05, .03]), 1)
    for i in range(n_orders):
        k = n_pay[i]
        if k == 1:
            parts = [totals[i]]
        else:
            w = rng.dirichlet(np.ones(k))
            parts = np.round(w * totals[i], 2)
            parts[-1] = round(totals[i] - parts[:-1].sum(), 2)
        for j, val in enumerate(parts, start=1):
            pay_rows.append((oids[i], j,
                             ptype_main[i] if j == 1 else "voucher",
                             int(inst[i]) if j == 1 else 1,
                             float(max(val, 0.0))))
    payments = pd.DataFrame(pay_rows, columns=[
        "order_id", "payment_sequential", "payment_type",
        "payment_installments", "payment_value"])

    # ------------------------------------------------------------------ reviews
    has_review = rng.random(n_orders) < 0.86
    r_idx = np.where(has_review)[0]
    late_r = is_late[r_idx]
    score = np.where(
        late_r,
        rng.choice([1, 2, 3, 4, 5], len(r_idx), p=[.42, .21, .17, .12, .08]),
        rng.choice([1, 2, 3, 4, 5], len(r_idx), p=[.06, .04, .09, .21, .60]))
    creation = purchase.to_numpy()[r_idx] + pd.to_timedelta(
        transit[r_idx] + 1, unit="D")
    reviews = pd.DataFrame({
        "review_id": _ids(rng, len(r_idx)),
        "order_id": oids[r_idx],
        "review_score": score,
        "review_comment_title": np.where(rng.random(len(r_idx)) < 0.12,
                                         "recomendo", None),
        "review_comment_message": np.where(rng.random(len(r_idx)) < 0.42,
                                           "produto chegou conforme o esperado", None),
        "review_creation_date": creation,
        "review_answer_timestamp": creation + pd.to_timedelta(
            rng.integers(1, 96, len(r_idx)), unit="h"),
    })

    # -------------------------------------------------------------- geolocation
    zips = np.unique(np.concatenate([customers["customer_zip_code_prefix"],
                                     sellers["seller_zip_code_prefix"]]))
    reps = rng.integers(1, 5, len(zips))            # 1:N – классическая ловушка JOIN
    gz = np.repeat(zips, reps)
    geo = pd.DataFrame({
        "geolocation_zip_code_prefix": gz,
        "geolocation_lat": np.round(-23.5 + rng.normal(0, 4.5, len(gz)), 6),
        "geolocation_lng": np.round(-46.6 + rng.normal(0, 5.0, len(gz)), 6),
        "geolocation_city": rng.choice(sum(CITIES.values(), []), len(gz)),
        "geolocation_state": rng.choice(STATES, len(gz)),
    })

    translation = pd.DataFrame(CATEGORIES, columns=[
        "product_category_name", "product_category_name_english"])

    # =================================================================
    #  Намеренные дефекты качества
    # =================================================================
    n_ = len(order_items)
    # 1. нулевые и отрицательные цены
    bad = rng.choice(n_, 18, replace=False)
    order_items.loc[bad[:9], "price"] = 0.0
    order_items.loc[bad[9:], "price"] = -order_items.loc[bad[9:], "price"].abs()
    # 2. отрицательная доставка
    order_items.loc[rng.choice(n_, 11, replace=False), "freight_value"] = -1.0
    # 3. пропуски в справочнике товаров
    products.loc[rng.choice(n_products, 30, replace=False), "product_weight_g"] = np.nan
    products.loc[rng.choice(n_products, 22, replace=False), "product_category_name"] = None
    # 4. "грязные" города: регистр и лишние пробелы
    m = rng.random(n_cust) < 0.25
    customers.loc[m, "customer_city"] = customers.loc[m, "customer_city"].str.upper()
    m = rng.random(n_cust) < 0.10
    customers.loc[m, "customer_city"] = " " + customers.loc[m, "customer_city"] + "  "
    m = rng.random(n_sellers) < 0.2
    sellers.loc[m, "seller_city"] = sellers.loc[m, "seller_city"].str.title()
    # 5. status=delivered, но даты доставки нет
    delivered_idx = np.where(orders["order_status"].to_numpy() == "delivered")[0]
    orders.loc[rng.choice(delivered_idx, 14, replace=False),
               "order_delivered_customer_date"] = pd.NaT
    # 6. полные дубликаты строк в платежах
    payments = pd.concat([payments, payments.sample(35, random_state=seed)],
                         ignore_index=True)
    # 7. один review_id на два разных заказа
    dup_r = reviews.sample(20, random_state=seed).copy()
    dup_r["order_id"] = rng.choice(oids, len(dup_r))
    reviews = pd.concat([reviews, dup_r], ignore_index=True)
    # 8. позиции заказа, ссылающиеся на несуществующий товар
    orph = rng.choice(n_, 25, replace=False)
    order_items.loc[orph, "product_id"] = _ids(rng, 25)
    # 9. approved_at раньше purchase
    bad_ap = rng.choice(n_orders, 12, replace=False)
    orders.loc[bad_ap, "order_approved_at"] = \
        orders.loc[bad_ap, "order_purchase_timestamp"] - pd.Timedelta(days=2)
    # 10. заказы без позиций (в оригинале таких 775) и без платежей
    no_items = rng.choice(oids, 22, replace=False)
    order_items = order_items[~order_items["order_id"].isin(no_items)].reset_index(drop=True)
    payments = payments[payments["order_id"] != oids[0]].reset_index(drop=True)
    # 11. estimated_delivery раньше покупки
    bad_est = rng.choice(n_orders, 6, replace=False)
    orders.loc[bad_est, "order_estimated_delivery_date"] = \
        orders.loc[bad_est, "order_purchase_timestamp"] - pd.Timedelta(days=1)

    # ---------------------------------------------------------------- сохранение
    for c in ["order_purchase_timestamp", "order_approved_at",
              "order_delivered_carrier_date", "order_delivered_customer_date",
              "order_estimated_delivery_date"]:
        orders[c] = _fmt(orders[c])
    order_items["shipping_limit_date"] = _fmt(order_items["shipping_limit_date"])
    for c in ["review_creation_date", "review_answer_timestamp"]:
        reviews[c] = _fmt(pd.to_datetime(reviews[c]))

    orders = orders[["order_id", "customer_id", "order_status",
                     "order_purchase_timestamp", "order_approved_at",
                     "order_delivered_carrier_date",
                     "order_delivered_customer_date",
                     "order_estimated_delivery_date"]]

    files = {
        "olist_customers_dataset.csv": customers,
        "olist_orders_dataset.csv": orders,
        "olist_order_items_dataset.csv": order_items,
        "olist_order_payments_dataset.csv": payments,
        "olist_order_reviews_dataset.csv": reviews,
        "olist_products_dataset.csv": products,
        "olist_sellers_dataset.csv": sellers,
        "olist_geolocation_dataset.csv": geo,
        "product_category_name_translation.csv": translation,
    }
    for name, df in files.items():
        df.to_csv(out / name, index=False)
    (out / "_SOURCE.txt").write_text(
        "synthetic (offline fallback, schema-compatible with Olist)\n"
        f"seed={seed} n_orders={n_orders}\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys
    from paths import RAW_OLIST
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print("generated ->", generate(RAW_OLIST, n_orders=n))
