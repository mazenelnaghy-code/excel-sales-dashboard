"""Create a year of sample sales data to try the dashboard on.

Usage:
    python make_sample_sales.py        # writes data/sales_2025.xlsx

About 4,000 orders from a fictional retailer with five branches, sold in store and online. The numbers
follow realistic patterns: busier during Ramadan, Eid and White Friday, quieter in the summer, and online
sales growing through the year.
"""
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

OUT = Path("data/sales_2025.xlsx")
BRANCHES = {"Cairo": 0.32, "Alexandria": 0.22, "Giza": 0.18, "Mansoura": 0.14, "Port Said": 0.14}
PRODUCTS = {
    "Electronics": [("Wireless earbuds", 1450), ("Smart watch", 3200), ("Power bank", 650), ("Bluetooth speaker", 1100)],
    "Home": [("Air fryer", 2800), ("Blender", 1350), ("Bed sheet set", 900), ("Desk lamp", 450)],
    "Fashion": [("Sneakers", 1600), ("Denim jacket", 1250), ("Handbag", 1900), ("Cotton T-shirt", 300)],
    "Beauty": [("Perfume", 1150), ("Skincare set", 850), ("Hair dryer", 1050)],
}
CATEGORY_WEIGHTS = {"Electronics": 0.27, "Home": 0.25, "Fashion": 0.30, "Beauty": 0.18}
# Orders per day, by month: Ramadan and Eid al-Fitr (March), Eid al-Adha (June), back to school
# (September) and White Friday (November) are busy; July and August are quiet.
DAILY_ORDERS = {1: 9, 2: 9, 3: 15, 4: 11, 5: 10, 6: 13, 7: 8, 8: 8, 9: 12, 10: 10, 11: 17, 12: 13}


def make_orders(seed=11):
    rng = random.Random(seed)
    rows, day, number = [], date(2025, 1, 1), 100001
    while day.year == 2025:
        weekend = day.weekday() in (3, 4)  # Thursday and Friday are the busiest shopping days
        count = max(0, round(rng.gauss(DAILY_ORDERS[day.month] * (1.25 if weekend else 1), 2.5)))
        online_share = 0.18 + 0.17 * (day.timetuple().tm_yday / 365)
        for _ in range(count):
            category = rng.choices(list(CATEGORY_WEIGHTS), weights=CATEGORY_WEIGHTS.values())[0]
            product, price = rng.choice(PRODUCTS[category])
            qty = rng.choices([1, 2, 3, 4], weights=[70, 20, 7, 3])[0]
            rows.append({
                "order_id": f"SO-{number}",
                "order_date": day,
                "branch": rng.choices(list(BRANCHES), weights=BRANCHES.values())[0],
                "channel": "Online" if rng.random() < online_share else "Store",
                "category": category,
                "product": product,
                "quantity": qty,
                "unit_price": float(price),
                "total": float(price * qty),
            })
            number += 1
        day += timedelta(days=1)
    return pd.DataFrame(rows)


def main(out=OUT):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    orders = make_orders()
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    with pd.ExcelWriter(out, engine="openpyxl") as xl:
        orders.to_excel(xl, sheet_name="Sales", index=False)
        ws = xl.sheets["Sales"]
        ws.freeze_panes = "A2"
        for cell in ws["B"][1:]:
            cell.number_format = "yyyy-mm-dd"
    print(f"Wrote {len(orders):,} orders, {orders['total'].sum():,.0f} EGP, to {out}")


if __name__ == "__main__":
    main()
