"""Tests for the continuous-contract builder (hand-computed rolls)."""

from datetime import datetime, timezone

import pytest

from trade_data_futures.continuous import ContractSeries, build_continuous
from trade_data_futures.models import FuturesBar, FuturesContract


def _bars(code, closes, volumes, start_day=1):
    return tuple(
        FuturesBar(
            contract_code=code,
            timestamp=datetime(2024, 1, start_day + i, tzinfo=timezone.utc),
            open=c, high=c, low=c, close=c, volume=v, open_interest=100.0,
        )
        for i, (c, v) in enumerate(zip(closes, volumes))
    )


def _series():
    # Front: Jan 1-5, closes 100..104, flat volume 100.
    # Next:  Jan 3-7, closes 105..109, volume crosses on Jan 4.
    front = ContractSeries(
        contract=FuturesContract("ES", 2024, 3),
        bars=_bars("ESH24", [100, 101, 102, 103, 104], [100] * 5, start_day=1),
    )
    nxt = ContractSeries(
        contract=FuturesContract("ES", 2024, 6),
        bars=_bars("ESM24", [105, 106, 107, 108, 109], [50, 150, 200, 200, 200], start_day=3),
    )
    return front, nxt


def test_volume_roll_ratio_adjust():
    out = build_continuous(list(_series()), roll="volume", adjust="ratio")
    # Roll date Jan 4: r = 106/103 back-adjusts Jan 1-3.
    r = 106 / 103
    closes = [b.close for b in out]
    assert closes == pytest.approx([100 * r, 101 * r, 102 * r, 106, 107, 108, 109])
    assert [b.contract_code for b in out] == ["ES=F"] * 7
    assert [b.source_contract for b in out] == ["ESH24"] * 3 + ["ESM24"] * 4
    # Volume/OI come from the active contract, never adjusted.
    assert [b.volume for b in out] == [100, 100, 100, 150, 200, 200, 200]
    assert all(b.open_interest == 100.0 for b in out)


def test_volume_roll_difference_adjust():
    out = build_continuous(list(_series()), roll="volume", adjust="difference")
    closes = [b.close for b in out]
    assert closes == pytest.approx([103, 104, 105, 106, 107, 108, 109])


def test_no_adjust_keeps_gaps():
    out = build_continuous(list(_series()), roll="volume", adjust="none")
    closes = [b.close for b in out]
    assert closes == pytest.approx([100, 101, 102, 106, 107, 108, 109])


def test_calendar_roll():
    front, nxt = _series()
    front = ContractSeries(
        contract=FuturesContract("ES", 2024, 3, expiry=datetime(2024, 1, 6).date()),
        bars=front.bars,
    )
    out = build_continuous([front, nxt], roll="calendar", roll_days_before=2, adjust="ratio")
    # Expiry Jan 6 - 2 days = Jan 4 roll: identical to the volume case.
    r = 106 / 103
    assert [b.close for b in out] == pytest.approx([100 * r, 101 * r, 102 * r, 106, 107, 108, 109])


def test_ratio_falls_back_to_difference_on_nonpositive():
    # Negative front close makes ratio meaningless -> difference step.
    front = ContractSeries(
        contract=FuturesContract("CL", 2024, 3),
        bars=_bars("CLH24", [-5.0, -4.0], [100, 100], start_day=1),
    )
    nxt = ContractSeries(
        contract=FuturesContract("CL", 2024, 4),
        bars=_bars("CLJ24", [20.0, 21.0], [50, 150], start_day=1),
    )
    out = build_continuous([front, nxt], roll="volume", adjust="ratio")
    # Roll on Jan 2 (150 > 100); d = 21 - (-4) = 25 -> Jan 1: -5 + 25 = 20.
    assert [b.close for b in out] == pytest.approx([20.0, 21.0])


def test_single_series_tagged_continuous():
    (front, _) = _series()
    out = build_continuous([front])
    assert [b.close for b in out] == pytest.approx([100, 101, 102, 103, 104])
    assert all(b.contract_code == "ES=F" and b.source_contract == "ESH24" for b in out)


def test_empty_input():
    assert build_continuous([]) == []


def test_invalid_options_rejected():
    (front, nxt) = _series()
    with pytest.raises(ValueError):
        build_continuous([front, nxt], roll="vibes")
    with pytest.raises(ValueError):
        build_continuous([front, nxt], adjust="spline")
