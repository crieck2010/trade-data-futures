"""Tests for futures month codes and contract-code symbology."""

import pytest

from trade_data_futures.exceptions import SymbolParseError
from trade_data_futures.symbols import (
    build_contract_code,
    month_code,
    month_from_code,
    parse_contract_code,
)


def test_all_twelve_month_codes_round_trip():
    codes = "FGHJKMNQUVXZ"
    for month, code in enumerate(codes, start=1):
        assert month_code(month) == code
        assert month_from_code(code) == month


def test_month_code_rejects_bad_input():
    with pytest.raises(SymbolParseError):
        month_code(0)
    with pytest.raises(SymbolParseError):
        month_code(13)
    with pytest.raises(SymbolParseError):
        month_from_code("A")


def test_build_and_parse_round_trip():
    for root, year, month in [("ES", 2025, 12), ("CL", 2026, 1), ("6E", 2025, 9), ("ZC", 2027, 3)]:
        code = build_contract_code(root, year, month)
        assert parse_contract_code(code) == (root, year, month)


def test_known_codes():
    assert build_contract_code("ES", 2025, 12) == "ESZ25"
    assert parse_contract_code("ESZ25") == ("ES", 2025, 12)
    assert parse_contract_code("6EZ25") == ("6E", 2025, 12)
    assert parse_contract_code("CLH2026") == ("CL", 2026, 3)
    assert parse_contract_code("esz25") == ("ES", 2025, 12)  # case-insensitive


def test_parse_rejects_malformed():
    for bad in ["ES", "ES25", "ESX9", "ESZ2", "ESZ123", ""]:
        with pytest.raises(SymbolParseError):
            parse_contract_code(bad)
