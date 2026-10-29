import sys
from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import make_sample_sales  # noqa: E402
import sales  # noqa: E402


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    path = tmp_path_factory.mktemp("data") / "sales.xlsx"
    make_sample_sales.main(path)
    return sales.load(path)


def test_sample_is_read_with_every_column(data):
    assert list(data.columns) == ["date", "revenue", "branch", "channel", "category", "product", "quantity", "order_id"]
    assert data["date"].dt.year.unique().tolist() == [2025]
    assert (data["revenue"] > 0).all()


def test_other_column_names_and_messy_values_are_understood():
    raw = pd.DataFrame({
        "Order Date": ["05/01/2025", "2025-01-06", "7 Jan 2025", "not a date"],
        "Amount": ["EGP 1,200", "300", 450, "100"],
        "City": ["Cairo", "Giza", "Cairo", "Giza"],
    })
    df = sales.standardise(raw)
    assert df["date"].dt.date.tolist() == [date(2025, 1, 5), date(2025, 1, 6), date(2025, 1, 7)]  # day first, ISO as is
    assert df["revenue"].tolist() == [1200.0, 300.0, 450.0]
    assert df["branch"].tolist() == ["Cairo", "Giza", "Cairo"]


def test_csv_upload(tmp_path):
    path = tmp_path / "export.csv"
    pd.DataFrame({"date": ["2025-02-01"], "sales": [99.5]}).to_csv(path, index=False)
    assert sales.load(path)["revenue"].tolist() == [99.5]


def test_missing_columns_are_named():
    with pytest.raises(sales.MissingColumns, match="revenue"):
        sales.standardise(pd.DataFrame({"date": ["2025-01-01"], "customer": ["Sara"]}))


def test_filters(data):
    march = sales.apply_filters(data, date(2025, 3, 1), date(2025, 3, 31), branch=["Cairo"], channel=[])
    assert march["date"].dt.month.unique().tolist() == [3]
    assert march["branch"].unique().tolist() == ["Cairo"]
    last_day = sales.apply_filters(data, date(2025, 12, 31), date(2025, 12, 31))
    assert last_day["date"].dt.date.unique().tolist() == [date(2025, 12, 31)]  # the end day is included


def test_kpis_add_up(data):
    k = sales.kpis(data)
    assert k["revenue"] == pytest.approx(data["revenue"].sum())
    assert k["orders"] == data["order_id"].nunique()
    assert k["avg_order"] == pytest.approx(k["revenue"] / k["orders"])


def test_previous_period_is_the_same_length_just_before(data):
    prev = sales.previous_period(data, date(2025, 3, 1), date(2025, 3, 31))
    assert prev["date"].min().date() == date(2025, 1, 29)
    assert prev["date"].max().date() == date(2025, 2, 28)
    assert sales.previous_period(data, date(2025, 1, 1), date(2025, 1, 31)) is None  # no data before January


def test_short_money():
    assert sales.short_money(8_047_400) == "8.05M EGP"
    assert sales.short_money(615_300) == "615K EGP"
    assert sales.short_money(999_500) == "1M EGP"
    assert sales.short_money(950) == "950 EGP"


def test_change():
    assert sales.change(110, 100) == pytest.approx(10)
    assert sales.change(5, 0) is None and sales.change(5, None) is None


def test_monthly_and_rankings(data):
    month = sales.monthly(data, split_by="channel")
    assert set(month["channel"]) == {"Online", "Store"}
    assert month["revenue"].sum() == pytest.approx(data["revenue"].sum())
    top = sales.revenue_by(data, "product", top=10)
    assert len(top) == 10 and top["revenue"].is_monotonic_decreasing


def test_excel_download_round_trips(data):
    back = pd.read_excel(BytesIO(sales.to_excel(data.head(20))))
    assert len(back) == 20
