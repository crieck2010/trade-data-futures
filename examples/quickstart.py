"""End-to-end smoke test: contracts, continuous bars, and curve math.

Requires the yfinance extra and network access:
    pip install "trade-data-futures[yfinance]"
"""

from datetime import date, timedelta

from trade_data_futures import (
    ContractCalendar,
    FuturesDataClient,
    Timeframe,
    YFinanceFuturesProvider,
    build_curve,
    curve_state,
    CurvePoint,
    fair_value,
    get_spec,
)


def main() -> None:
    spec = get_spec("ES")
    print(f"ES: {spec.description} | {spec.exchange} | ${spec.tick_value:.2f}/tick | "
          f"${spec.multiplier:.0f}/point")

    cal = ContractCalendar(root="ES")
    contracts = cal.upcoming(4)
    print("Upcoming ES contracts:", [c.contract_code for c in contracts])

    client = FuturesDataClient(YFinanceFuturesProvider())
    end = date.today()
    start = end - timedelta(days=30)
    bars = client.get_continuous("ES", Timeframe.DAILY, start, end)
    print(f"Continuous ES=F: {len(bars)} daily bars, "
          f"{bars[0].timestamp.date()} -> {bars[-1].timestamp.date()}, "
          f"last close {bars[-1].close:.2f} (from {bars[-1].source_contract})")

    # Cost-of-carry sanity: fair value of the front contract.
    front = contracts[0]
    t = max((front.expiry - end).days, 1) / 365
    print(f"Front {front.contract_code} fair value @ 4% carry: "
          f"{fair_value(bars[-1].close, 0.04, t):.2f}")

    # Synthetic curve demo (per-contract settles need a paid feed).
    curve = build_curve([
        CurvePoint("ESH25", date(2025, 3, 21), 5900.0),
        CurvePoint("ESM25", date(2025, 6, 20), 5935.0),
        CurvePoint("ESU25", date(2025, 9, 19), 5970.0),
    ])
    print("Curve state:", curve_state(curve),
          "| front roll yield:", f"{curve[0].roll_yield_annualized:.2%}")


if __name__ == "__main__":
    main()
