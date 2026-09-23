"""Tests for models, reference specs, and expiry calendars."""

from datetime import date, datetime, timezone

import pytest

from trade_data_futures.calendar import ContractCalendar, approximate_expiry
from trade_data_futures.exceptions import UnknownRootError
from trade_data_futures.models import (
    FuturesBar,
    FuturesContract,
    Settlement,
    Timeframe,
)
from trade_data_futures.specs import get_spec, known_roots, register_spec


def _bar(**kw):
    base = dict(
        contract_code="ESZ25",
        timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
        open=100.0, high=102.0, low=99.0, close=101.0,
        volume=1000.0, open_interest=5000.0,
    )
    base.update(kw)
    return FuturesBar(**base)


def test_spec_tick_values():
    es = get_spec("ES")
    assert es.tick_value == pytest.approx(12.50)
    assert es.settlement is Settlement.CASH
    assert get_spec("6E").tick_value == pytest.approx(6.25)
    assert get_spec("ZC").tick_value == pytest.approx(12.50)
    assert get_spec("ZB").tick_value == pytest.approx(31.25)
    assert get_spec("CL").tick_value == pytest.approx(10.0)


def test_spec_pnl():
    es = get_spec("ES")
    assert es.pnl(5000, 5010) == pytest.approx(500.0)  # 10 pts * $50
    assert es.pnl(5000, 4990, quantity=2) == pytest.approx(-1000.0)


def test_unknown_root_raises_and_registers():
    with pytest.raises(UnknownRootError):
        get_spec("NOPE")
    assert "ES" in known_roots()


def test_contract_code_property():
    c = FuturesContract(root="es", year=2025, month=12)
    assert c.contract_code == "ESZ25"
    assert str(c) == "ESZ25"
    assert c.root == "ES"


def test_bar_allows_negative_prices():
    # WTI printed -$37 in April 2020; the model must not reject history.
    b = _bar(open=-5.0, high=1.0, low=-10.0, close=-2.0)
    assert b.close == -2.0


def test_bar_rejects_bad_ohlc_and_nan():
    with pytest.raises(ValueError):
        _bar(open=103.0)  # open > high
    with pytest.raises(ValueError):
        _bar(close=float("nan"))
    with pytest.raises(ValueError):
        _bar(volume=-1.0)


def test_bar_utc_normalization():
    b = _bar(timestamp=datetime(2024, 1, 2, 12, 0))  # naive
    assert b.timestamp.tzinfo is not None


def test_calendar_upcoming_es_quarterly():
    cal = ContractCalendar(root="ES")
    contracts = cal.upcoming(4, from_date=date(2025, 1, 15))
    assert [c.contract_code for c in contracts] == ["ESH25", "ESM25", "ESU25", "ESZ25"]
    assert all(c.spec is cal.spec for c in contracts)


def test_calendar_upcoming_cl_monthly():
    contracts = ContractCalendar(root="CL").upcoming(3, from_date=date(2025, 1, 15))
    assert [c.contract_code for c in contracts] == ["CLG25", "CLH25", "CLJ25"]


def test_calendar_skips_expired():
    contracts = ContractCalendar(root="ES").upcoming(2, from_date=date(2025, 4, 1))
    assert contracts[0].contract_code == "ESM25"


def test_approximate_expiry_rules():
    # CME/CBOT: third Friday of the contract month.
    assert approximate_expiry("ES", 2025, 12) == date(2025, 12, 19)
    assert approximate_expiry("6E", 2025, 3) == date(2025, 3, 21)
    # NYMEX energy: last business day of the prior month.
    assert approximate_expiry("CL", 2025, 3) == date(2025, 2, 28)
    assert approximate_expiry("GC", 2025, 1) == date(2024, 12, 31)


def test_front_month():
    front = ContractCalendar(root="ES").front_month(from_date=date(2025, 1, 15))
    assert front.contract_code == "ESH25"
