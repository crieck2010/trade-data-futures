# trade-data-futures

Futures market-data engine: contract specifications, CME symbology, expiry
calendars, continuous-contract construction, cost-of-carry pricing, and
term-structure analytics. Third data module of the algorithmic/agentic
trading system — a sibling of `trade-data-equities` and
`trade-data-options`, sharing their provider/client/cache design language.

Free delayed data today (yfinance continuous front-month, ~15 minutes),
pluggable paid feeds tomorrow. Built for **research, backtesting, and
paper trading** — not for live execution.

## Features

- **Contract specs** — reference table for 20 common roots (ES, NQ, CL,
  GC, ZC, 6E, ZB, ZN, ...): exchange, multiplier, tick size/value, P&L
  math, settlement, listing cycle. Extensible via `register_spec`.
- **CME symbology** — month codes and contract-code build/parse
  (`ESZ25`, `6EZ25`).
- **Expiry calendars** — generate listed contracts with documented
  approximate last-trading dates; skip expired months automatically.
- **Continuous contracts** — stitch per-contract bars into `ES=F`-style
  front-month series with volume- or calendar-based rolls and
  ratio/difference back-adjustment (affine-composed, with difference
  fallback on non-positive prices). Volume/OI never adjusted;
  `source_contract` provenance on every bar.
- **Cost of carry** — fair value `F = S·e^(carry·T)`, implied carry, basis.
- **Term-structure analytics** — curve segments, annualized roll yield,
  contango/backwardation classification.
- **Disk cache** — bars and contract lists (24 h TTLs); stdlib-only JSON.
- **Bounded-memory streaming** — `stream_bars` walks long histories in
  date chunks.

## Installation

```bash
pip install trade-data-futures              # core engine, stdlib only
pip install "trade-data-futures[yfinance]"  # + free delayed front-month data
```

Requires Python 3.10+.

## Quickstart

```python
from datetime import date, timedelta
from trade_data_futures import (
    ContractCalendar, FuturesDataClient, Timeframe,
    YFinanceFuturesProvider, get_spec,
)

spec = get_spec("ES")
print(f"${spec.tick_value:.2f} per tick")  # $12.50

# Listed contracts from the calendar.
contracts = ContractCalendar(root="ES").upcoming(4)
print([c.contract_code for c in contracts])  # ['ESH26', 'ESM26', ...]

client = FuturesDataClient(YFinanceFuturesProvider())
end = date.today()
bars = client.get_continuous("ES", Timeframe.DAILY, end - timedelta(days=90), end)
print(f"{len(bars)} bars, last close {bars[-1].close:.2f} "
      f"(from {bars[-1].source_contract})")

# P&L for a 10-point ES move.
print(spec.pnl(5000, 5010))  # 500.0 USD
```

## Architecture

```
                        ┌──────────────────────┐
                        │  FuturesDataClient   │  contracts · bars · continuous
                        └──────────┬───────────┘
              ┌────────────────────┼─────────────────────┐
              ▼                    ▼                     ▼
   ┌──────────────────┐  ┌─────────────────┐  ┌────────────────────┐
   │FuturesDataProvi- │  │    DiskCache    │  │ continuous (rolls) │
   │der (ABC)         │  │  JSON on disk   │  │ carry · curve      │
   └────────┬─────────┘  └─────────────────┘  │ calendar · specs   │
            ▼                                 │ symbols            │
   ┌───────────────────────┐                  └────────────────────┘
   │YFinanceFuturesProvider│  ← continuous front-month only
   └───────────────────────┘
   ┌───────────────────────┐
   │ YourProviderHere      │  ← implement 2 methods for per-contract data
   └───────────────────────┘

models: ContractSpec · FuturesContract · FuturesBar · Timeframe · Settlement
```

**Data flow.** `get_contracts` lists contracts (calendar-backed for
yfinance); `get_bars` fetches one contract's bars; `get_continuous`
fetches every listed contract and stitches them with `build_continuous`.

**Free-tier honesty.** Yahoo publishes futures as continuous front-month
series (`ES=F`), not per-contract histories. The yfinance adapter
therefore returns the continuous series for any requested contract and
tags bars with that contract's code — a front-month proxy, not true
per-contract data. `build_continuous` does the real stitching and shines
with paid per-contract feeds (same two-method provider interface).

## Continuous contracts

```python
from trade_data_futures import ContractSeries, build_continuous

series = [
    ContractSeries(contract=c, bars=tuple(
        client.get_bars(c, Timeframe.DAILY, start, end, use_cache=False)))
    for c in contracts
]
cont = build_continuous(series, roll="volume", adjust="ratio")
```

- `roll="volume"`: switch when the next contract's volume exceeds the
  front's (the market's liquidity vote). `roll="calendar"`: switch
  `roll_days_before` days before each contract's `expiry`.
- `adjust="ratio"` multiplies history by `next_close/front_close` at each
  roll; `"difference"` adds the gap; `"none"` keeps raw gaps. Boundaries
  compose as affine transforms, so mixed ratio/difference rolls (e.g. the
  negative-price fallback) stay exact.
- Negative prices are first-class: bars accept them (WTI, Apr-2020), and
  ratio adjustment falls back to difference at non-positive boundaries.

## Cost of carry & curve

```python
from trade_data_futures import fair_value, implied_carry, build_curve, curve_state, CurvePoint

fair_value(spot=5900, carry=0.04, t_years=0.25)   # theoretical future
implied_carry(futures_price=5935, spot=5900, t_years=0.25)  # market-implied

curve = build_curve([CurvePoint("ESH26", date(2026, 3, 20), 5900.0), ...])
curve_state(curve)  # 'contango' | 'backwardation' | 'mixed'
curve[0].roll_yield_annualized  # what a long pays/earns rolling
```

## Adding a provider

```python
from trade_data_futures import FuturesDataProvider

class MyFeed(FuturesDataProvider):
    name = "myfeed"
    delay_minutes = 0

    def get_contracts(self, root: str, n: int = 12) -> list[FuturesContract]: ...
    def get_bars(self, contract, timeframe, start, end) -> list[FuturesBar]: ...
```

Return true per-contract bars (with volume *and* open interest) and the
client, cache, continuous builder, and curve analytics work unchanged.

## Interop with trade-data-equities / trade-data-options

The engines are decoupled — this package imports neither sibling — but
they compose:

```python
from trade_data_futures import FuturesDataClient, YFinanceFuturesProvider, get_spec

fut = FuturesDataClient(YFinanceFuturesProvider())
bars = fut.get_continuous("ES", Timeframe.DAILY, start, end)

# FuturesBar mirrors the equity Bar shape (timestamp, OHLC, volume) plus
# open_interest and contract_code, so downstream engines (trade-backtest,
# trade-strategies) can treat them uniformly.
for b in bars[-5:]:
    print(b.timestamp.date(), b.close, b.open_interest)

# Futures on single stocks pair with equity bars by date for basis work;
# options on futures (e.g. CME) reuse trade-data-options' pricing once a
# futures-price feed is passed as the "spot".
```

`ContractSpec.tick_value` / `pnl` give `trade-risk` the notional and
per-tick exposure math it needs for futures sizing.

## Scaling notes

- **Per-contract caching** means a 12-contract stitch fetches each series
  once; `stream_bars` keeps memory flat over multi-year histories.
- **Roll math is pure** — `build_continuous` is a pure function over bar
  lists, trivially parallelizable per root and replayable in backtests.
- **Throughput:** one client per thread; workers share a `DiskCache` root
  (`TRADE_FUTURES_CACHE`); writes are atomic per key.
- yfinance is one HTTP call per contract request; the provider throttles
  (default 0.5 s) and retries with backoff.

## API reference (essentials)

| Name | Kind | Purpose |
|---|---|---|
| `FuturesDataClient(provider, cache)` | class | Main entry point |
| `client.get_contracts(root, n)` | method | Listed contracts, nearest first |
| `client.get_contract(code)` | method | Resolve `ESZ25` |
| `client.get_bars(contract, timeframe, start, end)` | method | Per-contract bars `[start, end)` |
| `client.get_continuous(root, timeframe, start, end, ...)` | method | Stitched front-month series |
| `client.stream_bars(...)` | method | Chunked iteration |
| `build_continuous(series, roll, adjust)` | function | Stitch per-contract bars |
| `ContractCalendar(root).upcoming(n)` | method | Listed contract months |
| `get_spec` / `register_spec` / `known_roots` | functions | Contract specifications |
| `fair_value` / `implied_carry` / `basis` | functions | Cost of carry |
| `build_curve` / `curve_state` | functions | Term-structure analytics |
| `build_contract_code` / `parse_contract_code` | functions | Symbology |

## Testing

```bash
pip install "trade-data-futures[dev]"
pytest -q
```

Fully offline: roll/adjustment cases are hand-computed, providers are
faked, and calendars are checked against known expiry dates.
`examples/quickstart.py` is the live smoke test (needs the `yfinance`
extra and network).

## Roadmap

Sibling repositories:

- `trade-data-equities` — stock/ETF bars (done)
- `trade-data-options` — chains, Greeks, IV surfaces (done)
- `trade-data-futures` — this repo
- `trade-data-crypto` — 24/7 exchange data
- `trade-backtest` — event-driven backtesting
- `trade-strategies` — strategy framework + starters
- `trade-risk` — position sizing, limits, drawdown guards
- `trade-agents` — hedge-fund desk: idea agents → portfolio-manager → risk-manager
- `trade-dashboard-web` / `trade-dashboard-desktop` — dashboards
- `trade-suite` — meta-package tying it all together

## The maths

**What you learn.** Futures have no single price series — each contract dies at expiry — so this engine's core maths is *synthesis*: stitching per-contract bars into continuous series, pricing the cost of carry, and reading the term structure. Plus the contract-spec arithmetic (tick value, P&L) that turns point moves into dollars.

**Why it matters.** A naive concatenation of contract histories shows a fake gap at every roll; backtests on it invent profits at boundaries that never existed. Back-adjustment removes the roll gap while preserving every bar-to-bar return, so momentum, volatility, and drawdown statistics on the continuous series are the statistics of a rolled position — which is what you actually trade.

**The maths.** Continuous construction: at each roll boundary, `adjust="ratio"` multiplies all earlier history by `next_close / front_close` (affine: `P ← a·P`), `"difference"` adds the gap (`P ← P + d`), `"none"` keeps raw gaps; boundaries compose as affine transforms, so mixed ratio/difference rolls stay exact. Roll timing is volume-based (switch when the next contract's volume exceeds the front's — the market's liquidity vote) or calendar-based (`roll_days_before` ahead of expiry). Negative prices are first-class: ratio adjustment falls back to difference at non-positive boundaries (WTI, Apr-2020). Volume and open interest are never adjusted; every bar carries `source_contract` provenance. Cost of carry: fair value `F = S·e^(carry·T)`, implied carry `ln(F/S)/T`, basis `F − S`. Term structure: consecutive contracts form segments with annualized roll yield `(F_far/F_near − 1)·(365/days)`; the curve is `contango` when all segments slope up, `backwardation` when all slope down, else `mixed`. Spec maths: `tick_value = multiplier × tick_size` (ES: $12.50/tick), `pnl = (exit − entry) × multiplier × quantity`.

**Honest limitations.** Expiry calendars use documented *approximate* last-trading dates — verify against the exchange for production use. The yfinance feed publishes only continuous front-month series, so its "per-contract" bars are a front-month proxy, not true stitching input; real `build_continuous` value needs a per-contract feed. Back-adjusted prices are not tradable prices — never read absolute levels off an adjusted series, only returns. Roll yield annualization is a linear approximation, not a compounded rate.

## License

MIT — see [LICENSE](LICENSE).
