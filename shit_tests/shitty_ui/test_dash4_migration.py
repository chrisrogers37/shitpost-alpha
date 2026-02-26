"""
Dash 4.0 migration verification tests.

Ensures all Dash components used in the dashboard are compatible with
Dash 4.x and dash-bootstrap-components 2.x.
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))


class TestDash4Version:
    """Verify Dash 4.x and dbc 2.x are installed."""

    def test_dash_version_is_4x(self):
        """Dash version must be 4.x after migration."""
        import dash
        major = int(dash.__version__.split(".")[0])
        assert major == 4, f"Expected Dash 4.x, got {dash.__version__}"

    def test_dbc_version_is_2x(self):
        """dash-bootstrap-components version must be 2.x after migration."""
        import dash_bootstrap_components as dbc
        major = int(dbc.__version__.split(".")[0])
        assert major == 2, f"Expected dbc 2.x, got {dbc.__version__}"


class TestDash4ComponentInstantiation:
    """Verify all DCC components used in the app instantiate without error."""

    def test_dcc_slider(self):
        from dash import dcc
        slider = dcc.Slider(id="test-slider", min=0.0, max=1.0, step=0.05, value=0.7,
                           marks={0.0: "0%", 0.5: "50%", 1.0: "100%"})
        assert slider.id == "test-slider"
        assert slider.step == 0.05

    def test_dcc_range_slider(self):
        from dash import dcc
        slider = dcc.RangeSlider(id="test-range", min=0, max=1, step=0.05, value=[0, 1],
                                marks={0: "0", 0.5: "0.5", 1: "1"})
        assert slider.id == "test-range"
        assert slider.step == 0.05

    def test_dcc_dropdown_single(self):
        from dash import dcc
        dd = dcc.Dropdown(id="test-dropdown", options=[{"label": "25", "value": 25}],
                         value=25, clearable=False)
        assert dd.id == "test-dropdown"

    def test_dcc_dropdown_multi(self):
        from dash import dcc
        dd = dcc.Dropdown(id="test-multi-dd", options=[], value=[], multi=True,
                         placeholder="All assets")
        assert dd.id == "test-multi-dd"

    def test_dcc_datepicker_range(self):
        from dash import dcc
        from datetime import datetime, timedelta
        dp = dcc.DatePickerRange(id="test-datepicker",
                                start_date=(datetime.now() - timedelta(days=90)).date(),
                                end_date=datetime.now().date(), display_format="YYYY-MM-DD")
        assert dp.id == "test-datepicker"

    def test_dcc_loading(self):
        from dash import dcc, html
        loading = dcc.Loading(id="test-loading", type="default", color="#85BB65",
                             children=html.Div(id="test-child"))
        assert loading.id == "test-loading"

    def test_dcc_store(self):
        from dash import dcc
        store = dcc.Store(id="test-store", storage_type="local", data={"key": "value"})
        assert store.id == "test-store"

    def test_dcc_interval(self):
        from dash import dcc
        interval = dcc.Interval(id="test-interval", interval=5000, n_intervals=0)
        assert interval.id == "test-interval"

    def test_dcc_location(self):
        from dash import dcc
        loc = dcc.Location(id="test-url", refresh=False)
        assert loc.id == "test-url"

    def test_dash_table(self):
        from dash import dash_table
        table = dash_table.DataTable(data=[{"col": "value"}],
                                    columns=[{"name": "col", "id": "col"}],
                                    page_size=15, sort_action="native")
        assert table.page_size == 15


class TestDash4DashBootstrap:
    """Verify dbc components used in the app work with dbc 2.x."""

    def test_dbc_card(self):
        import dash_bootstrap_components as dbc
        card = dbc.Card(id="test-card")
        assert card.id == "test-card"

    def test_dbc_button(self):
        import dash_bootstrap_components as dbc
        btn = dbc.Button("Test", id="test-btn", color="primary")
        assert btn.id == "test-btn"

    def test_dbc_offcanvas(self):
        import dash_bootstrap_components as dbc
        oc = dbc.Offcanvas(id="test-offcanvas", title="Test", placement="end", is_open=False)
        assert oc.id == "test-offcanvas"

    def test_dbc_switch(self):
        import dash_bootstrap_components as dbc
        sw = dbc.Switch(id="test-switch", value=False)
        assert sw.id == "test-switch"

    def test_dbc_collapse(self):
        import dash_bootstrap_components as dbc
        col = dbc.Collapse(id="test-collapse", is_open=False)
        assert col.id == "test-collapse"

    def test_dbc_toast(self):
        import dash_bootstrap_components as dbc
        toast = dbc.Toast(id="test-toast", header="Test", is_open=False, icon="success")
        assert toast.id == "test-toast"

    def test_dbc_radio_items(self):
        import dash_bootstrap_components as dbc
        radio = dbc.RadioItems(id="test-radio", options=[{"label": "A", "value": "a"}], value="a")
        assert radio.id == "test-radio"
