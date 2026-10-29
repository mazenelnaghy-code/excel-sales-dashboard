"""Load a sales export (Excel or CSV) and compute everything the dashboard shows.

Column names don't have to match exactly: 'Date', 'Order Date' and 'invoice_date' are all read as the date,
'Total', 'Amount' and 'Revenue' as the revenue, and so on. Only a date and a revenue column are required;
branch, channel, category, product, quantity and order id unlock more of the dashboard when present.
"""
from io import BytesIO
from pathlib import Path

import pandas as pd

COLUMNS = {  # standard name -> names it may have in a client's file
    "date": ["order_date", "invoice_date", "sale_date", "day"],
    "revenue": ["total", "amount", "sales", "net_sales", "total_egp"],
    "branch": ["city", "store", "location", "region"],
    "channel": ["channel", "sales_channel"],
    "category": ["product_category", "department"],
    "product": ["item", "product_name", "sku"],
    "quantity": ["qty", "units"],
    "order_id": ["order", "order_no", "order_number", "invoice_no", "invoice", "invoice_number"],
}
REQUIRED = ("date", "revenue")


class MissingColumns(ValueError):
    pass


def normalise(name):
    """'Order Date', 'order-date' and 'order_date' all become 'order_date'."""
    return "_".join(str(name).strip().lower().replace("-", " ").split())


def to_number(column):
    """'EGP 1,200' -> 1200.0; numbers stay numbers; anything unreadable -> NaN."""
    if pd.api.types.is_numeric_dtype(column):
        return column
    return pd.to_numeric(column.astype(str).str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce")


def to_date(column):
    """ISO dates (2025-01-06) as written; everything else day-first (06/01/2025), as in Egypt."""
    text = column.astype(str).str.strip()
    iso = text.str.match(r"^\d{4}-\d{1,2}-\d{1,2}")
    dates = pd.to_datetime(text.where(~iso), errors="coerce", dayfirst=True, format="mixed")
    return dates.fillna(pd.to_datetime(text.where(iso), errors="coerce", format="ISO8601"))


def standardise(raw):
    """Rename the client's columns to the standard names and fix their types."""
    lookup = {normalise(c): c for c in raw.columns}
    found = {}
    for standard, names in COLUMNS.items():
        match = next((lookup[n] for n in [standard] + names if n in lookup), None)
        if match is not None:
            found[standard] = match
    missing = [c for c in REQUIRED if c not in found]
    if missing:
        raise MissingColumns(f"Could not find a {' or a '.join(missing)} column. "
                             f"Columns in the file: {', '.join(map(str, raw.columns))}")

    df = raw[list(found.values())].rename(columns={v: k for k, v in found.items()})
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = to_date(df["date"])
    for column in ("revenue", "quantity"):
        if column in df:
            df[column] = to_number(df[column])
    return df.dropna(subset=["date", "revenue"]).sort_values("date").reset_index(drop=True)


def load(source, name=None):
    """Read an .xlsx/.xls/.csv path or uploaded file and standardise it."""
    name = (name or getattr(source, "name", None) or str(source)).lower()
    raw = pd.read_csv(source) if name.endswith(".csv") else pd.read_excel(source)
    return standardise(raw)


def apply_filters(df, start, end, **choices):
    """Rows between start and end (inclusive), and in the chosen values of each column given."""
    keep = (df["date"] >= pd.Timestamp(start)) & (df["date"] < pd.Timestamp(end) + pd.Timedelta(days=1))
    for column, values in choices.items():
        if column in df and values:
            keep &= df[column].isin(values)
    return df[keep]


def previous_period(df, start, end, **choices):
    """The same filters over the same number of days just before `start`, to compare against."""
    days = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
    prev_end = pd.Timestamp(start) - pd.Timedelta(days=1)
    prev_start = prev_end - pd.Timedelta(days=days - 1)
    if prev_start < df["date"].min().normalize():
        return None  # not enough history for a fair comparison
    return apply_filters(df, prev_start, prev_end, **choices)


def kpis(df):
    orders = df["order_id"].nunique() if "order_id" in df else len(df)
    revenue = float(df["revenue"].sum())
    return {
        "revenue": revenue,
        "orders": int(orders),
        "avg_order": revenue / orders if orders else 0.0,
        "units": int(df["quantity"].sum()) if "quantity" in df else None,
    }


def change(now, before):
    """Percentage change, or None when there is nothing to compare."""
    if before in (None, 0):
        return None
    return (now - before) / before * 100


def monthly(df, split_by=None):
    """Revenue per month, optionally split by a column (e.g. channel)."""
    keys = [df["date"].dt.to_period("M").dt.to_timestamp().rename("month")]
    if split_by and split_by in df:
        keys.append(df[split_by])
    return df.groupby(keys)["revenue"].sum().reset_index()


def revenue_by(df, column, top=None):
    """Revenue per value of `column`, biggest first."""
    out = df.groupby(column)["revenue"].sum().sort_values(ascending=False).reset_index()
    return out.head(top) if top else out


def short_money(value, currency="EGP"):
    """8047400 -> '8.05M EGP': three significant figures, short enough for a KPI box on a laptop screen."""
    for size, unit in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= size * 0.9995:  # 999,500 rounds up to 1M, not to '1e+03K'
            return f"{value / size:.3g}{unit} {currency}"
    return f"{value:,.0f} {currency}"


def to_excel(df):
    """The rows as an .xlsx file in memory, for the download button."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name="Sales", index=False)
    return buffer.getvalue()


SAMPLE = Path(__file__).parent / "data" / "sales_2025.xlsx"
