"""Tests for the futures client and disk cache."""

from datetime import date, datetime, timedelta, timezone

import pytest

from trade_data_futures.cache import DiskCache
from trade_data_futures.client import FuturesDataClient
from trade_data_futures.continuous import ContractSeries
from trade_data_futures.exceptions import ContractNotFoundError
from trade_data_futures.models import FuturesBar, FuturesContract, Timeframe
from trade_data_futures.providers import FuturesDataProvider


def _bar(code, day, close, volume=100.0):
    return FuturesBar(
        contract_code=code,
        timestamp=datetime(2024, 1, day, tzinfo=timezone.utc),
        open=close, high=close, low=close, close=close,
        volume=volume, open_interest=50.0,
    )


class FakeFuturesProvider(FuturesDataProvider):
    name = "fake"

    def __init__(self):
        self.contracts_calls = 0
        self.bars_calls = []

    def get_contracts(self, root, n=12):
        self.contracts_calls += 1
        return [FuturesContract(root, 2024, m) for m in (3, 6, 9)][:n]

    def get_bars(self, contract, timeframe, start, end):
        self.bars_calls.append(contract.contract_code)
        base = 100.0 if contract.month == 3 else 105.0
        vols = [100.0, 100.0, 150.0] if contract.month == 6 else [100.0] * 3
        return [
            _bar(contract.contract_code, day, base + day, volume=v)
            for day, v in zip((1, 2, 3), vols)
        ]


def _client(provider, tmp_path):
    return FuturesDataClient(provider, cache=DiskCache(root=tmp_path))


def test_contracts_cached(tmp_path):
    provider = FakeFuturesProvider()
    client = _client(provider, tmp_path)
    first = client.get_contracts("ES")
    assert [c.contract_code for c in first] == ["ESH24", "ESM24", "ESU24"]
    client.get_contracts("ES")
    assert provider.contracts_calls == 1


def test_get_contract_resolves_code(tmp_path):
    client = _client(FakeFuturesProvider(), tmp_path)
    assert client.get_contract("ESH24").month == 3
    with pytest.raises(ContractNotFoundError):
        client.get_contract("ESZ25")


def test_bars_cached_and_deduped(tmp_path):
    provider = FakeFuturesProvider()
    client = _client(provider, tmp_path)
    bars = client.get_bars("ESH24", Timeframe.DAILY, date(2024, 1, 1), date(2024, 1, 10))
    assert len(bars) == 3
    assert bars[0].open_interest == 50.0
    client.get_bars("ESH24", Timeframe.DAILY, date(2024, 1, 1), date(2024, 1, 10))
    assert provider.bars_calls.count("ESH24") == 1


def test_get_continuous_stitches_contracts(tmp_path):
    client = _client(FakeFuturesProvider(), tmp_path)
    contracts = [FuturesContract("ES", 2024, 3), FuturesContract("ES", 2024, 6)]
    out = client.get_continuous(
        "ES", Timeframe.DAILY, date(2024, 1, 1), date(2024, 1, 10),
        contracts=contracts,
    )
    assert out, "expected stitched bars"
    assert all(b.contract_code == "ES=F" for b in out)
    # Mar series: closes 101,102,103; Jun series: 106,107,108; volume crosses day 3.
    assert [b.source_contract for b in out] == ["ESH24", "ESH24", "ESM24"]
    r = 108 / 103
    assert [b.close for b in out] == pytest.approx([101 * r, 102 * r, 108])


def test_get_continuous_continuous_only_provider(tmp_path):
    class ContinuousOnlyProvider(FakeFuturesProvider):
        serves_continuous_only = True

    provider = ContinuousOnlyProvider()
    client = _client(provider, tmp_path)
    out = client.get_continuous("ES", Timeframe.DAILY, date(2024, 1, 1), date(2024, 1, 10))
    # One fetch of the front contract's feed, tagged as the continuous series.
    assert provider.bars_calls == ["ESH24"]
    assert [b.close for b in out] == pytest.approx([101.0, 102.0, 103.0])
    assert all(b.contract_code == "ES=F" and b.source_contract == "ESH24" for b in out)


def test_stream_bars_chunks(tmp_path):
    client = _client(FakeFuturesProvider(), tmp_path)
    bars = list(client.stream_bars("ESH24", Timeframe.DAILY, date(2024, 1, 1), date(2024, 1, 10), chunk_days=2))
    assert len(bars) == 3 * 5  # 3 bars per 2-day chunk x 5 chunks


def test_cache_bars_round_trip(tmp_path):
    cache = DiskCache(root=tmp_path)
    bars = [_bar("ESH24", 1, 101.0), _bar("ESH24", 2, 102.0)]
    assert cache.get_bars("p", "ESH24", Timeframe.DAILY, date(2024, 1, 1), date(2024, 1, 5)) is None
    cache.put_bars("p", "ESH24", Timeframe.DAILY, date(2024, 1, 1), date(2024, 1, 5), bars)
    hit = cache.get_bars("p", "ESH24", Timeframe.DAILY, date(2024, 1, 1), date(2024, 1, 5))
    assert [b.close for b in hit] == [101.0, 102.0]
    assert hit[0].open_interest == 50.0


def test_cache_contracts_round_trip_and_ttl(tmp_path):
    cache = DiskCache(root=tmp_path, contracts_ttl=timedelta(seconds=0))
    contracts = [FuturesContract("ES", 2024, 3, expiry=date(2024, 3, 15))]
    cache.put_contracts("p", "ES", contracts)
    assert cache.get_contracts("p", "ES") is None  # expired immediately
    cache.contracts_ttl = timedelta(hours=1)
    cache.put_contracts("p", "ES", contracts)
    hit = cache.get_contracts("p", "es")
    assert [(c.root, c.year, c.month, c.expiry) for c in hit] == [("ES", 2024, 3, date(2024, 3, 15))]


def test_cache_clear(tmp_path):
    cache = DiskCache(root=tmp_path)
    cache.put_contracts("p", "ES", [FuturesContract("ES", 2024, 3)])
    assert cache.clear() == 1
