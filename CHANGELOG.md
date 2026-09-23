# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-23

### Added
- Core models: `ContractSpec` (multiplier, tick size/value, P&L math),
  `FuturesContract`, `FuturesBar` (OHLCV + open interest, negative prints
  allowed), `Timeframe`, `Settlement`.
- `symbols`: CME month codes and contract-code build/parse (`ESZ25`).
- `specs`: reference spec table for 20 common roots (ES, NQ, CL, GC, ZC,
  6E, ZB, ZN, ...), with `get_spec` / `register_spec` / `known_roots`.
- `calendar`: `ContractCalendar` generating listed contracts with
  documented approximate last-trading dates.
- `continuous`: `build_continuous` -- volume- or calendar-based rolls,
  ratio/difference back-adjustment composed as affine transforms (with
  difference fallback on non-positive prices), volume/OI never adjusted,
  `source_contract` provenance on every bar.
- `carry`: cost-of-carry fair value, implied carry, basis.
- `curve`: term-structure segments, annualized roll yield,
  contango/backwardation classification.
- `FuturesDataProvider` ABC; `YFinanceFuturesProvider` serving free
  delayed continuous front-month series (per-contract histories are a
  documented limitation of the free tier).
- `FuturesDataClient`: contracts, bars, `get_continuous`, chunked
  `stream_bars`; `DiskCache` (stdlib JSON, 24 h TTLs).
- Offline test suite with hand-computed roll/adjustment cases and a
  comprehensive README.
