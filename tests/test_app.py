from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture
def app():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception
    return at


def test_dashboard_shows_the_sample(app):
    assert [m.label for m in app.metric] == ["Revenue", "Orders", "Average order", "Units sold"]
    assert app.metric[0].value == "8.05M EGP"  # short enough not to be cut off on a laptop
    assert len(app.get("plotly_chart")) == 4
    assert "sample data" in app.caption[0].value


def test_filtering_a_branch_lowers_revenue(app):
    total = app.metric[0].value
    app.multiselect[0].select("Cairo").run()  # first filter is Branch
    assert not app.exception
    assert app.metric[0].value != total
    assert "of 4,328 rows" in app.caption[0].value


def test_a_month_is_compared_with_the_month_before(app):
    app.date_input[0].set_value((date(2025, 3, 1), date(2025, 3, 31))).run()
    assert not app.exception
    assert "vs previous period" in app.metric[0].delta
