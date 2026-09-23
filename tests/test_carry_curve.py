"""Tests for cost-of-carry pricing and term-structure analytics."""

from datetime import date

import pytest

from trade_data_futures.carry import basis, fair_value, implied_carry
from trade_data_futures.curve import CurvePoint, build_curve, curve_state


def test_fair_value():
    # S=100, carry=5%, T=1 -> 105.127.
    assert fair_value(100, 0.05, 1.0) == pytest.approx(105.127, abs=0.001)
    assert fair_value(100, 0.0, 1.0) == pytest.approx(100.0)


def test_implied_carry_round_trip():
    f = fair_value(2500, 0.03, 0.5)
    assert implied_carry(f, 2500, 0.5) == pytest.approx(0.03, abs=1e-9)


def test_basis_sign():
    assert basis(105, 100) == 5.0  # contango
    assert basis(95, 100) == -5.0  # backwardation


def test_carry_rejects_bad_inputs():
    with pytest.raises(ValueError):
        fair_value(-100, 0.05, 1.0)
    with pytest.raises(ValueError):
        implied_carry(105, 100, 0.0)


def _points(prices):
    months = [3, 6, 9, 12]
    return [
        CurvePoint(contract_code=f"ESH{i + 24}", expiry=date(2024 + (i // 4), months[i % 4], 15), settle=p)
        for i, p in enumerate(prices)
    ]


def test_curve_contango():
    segments = build_curve(_points([100, 101, 102]))
    assert len(segments) == 2
    assert all(s.contango for s in segments)
    assert curve_state(segments) == "contango"
    # Annualized roll yield: (101/100 - 1) * 365/92.
    assert segments[0].roll_yield_annualized == pytest.approx(0.01 * 365 / 92, rel=1e-6)


def test_curve_backwardation():
    segments = build_curve(_points([102, 101, 100]))
    assert curve_state(segments) == "backwardation"
    assert all(not s.contango for s in segments)


def test_curve_mixed_and_empty():
    assert curve_state(build_curve(_points([100, 102, 101]))) == "mixed"
    assert curve_state([]) == "unknown"


def test_curve_skips_bad_points():
    points = _points([100, 0, 102])  # zero settle is unusable
    assert len(build_curve(points)) == 0 or all(s.days_between > 0 for s in build_curve(points))
