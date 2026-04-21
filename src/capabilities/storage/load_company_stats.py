#!/usr/bin/env python3
"""Load company daily stats CSV into PostgreSQL."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for, write_guard


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = "stock_event_mining"
DEFAULT_INPUT = ROOT / "output" / "seeds" / "company_stats.csv"
DEFAULT_QUOTES_INPUT = ROOT / "output" / "seeds" / "stock_daily_quotes.csv"
CREATE_SQL_PATH = ROOT / "sql" / "create_training_support_tables.sql"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load company stats into PostgreSQL.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--quotes-input", default=str(DEFAULT_QUOTES_INPUT))
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    return parser.parse_args(argv)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    rows = read_rows(Path(args.input).resolve())
    quotes_path = Path(args.quotes_input).resolve()
    quote_rows = read_rows(quotes_path) if quotes_path.exists() else []

    with write_guard(
        db_name=args.db,
        required_tables=["companies", "model_event_samples"],
        lock_timeout_sec=args.lock_timeout_sec,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_SQL_PATH.read_text(encoding="utf-8"))
            for row in quote_rows:
                cur.execute(
                    """
                    INSERT INTO stock_daily_quotes (
                        ts_code, trade_date, open, high, low, close, pre_close, pct_chg,
                        volume, amount, turnover_rate, adj_factor, is_suspended, is_st,
                        is_limit_up, is_limit_down, data_source
                    )
                    VALUES (
                        %s, %s, NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric,
                        NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric,
                        NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric,
                        NULLIF(%s, '')::numeric, %s::boolean, %s::boolean, %s::boolean, %s::boolean, %s
                    )
                    ON CONFLICT (ts_code, trade_date) DO UPDATE
                    SET
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        pre_close = EXCLUDED.pre_close,
                        pct_chg = EXCLUDED.pct_chg,
                        volume = EXCLUDED.volume,
                        amount = EXCLUDED.amount,
                        turnover_rate = EXCLUDED.turnover_rate,
                        adj_factor = EXCLUDED.adj_factor,
                        is_suspended = EXCLUDED.is_suspended,
                        is_st = EXCLUDED.is_st,
                        is_limit_up = EXCLUDED.is_limit_up,
                        is_limit_down = EXCLUDED.is_limit_down,
                        data_source = EXCLUDED.data_source,
                        updated_at = NOW()
                    """,
                    (
                        row["ts_code"],
                        row["trade_date"],
                        row.get("open", ""),
                        row.get("high", ""),
                        row.get("low", ""),
                        row.get("close", ""),
                        row.get("pre_close", ""),
                        row.get("pct_chg", ""),
                        row.get("volume", ""),
                        row.get("amount", ""),
                        row.get("turnover_rate", ""),
                        row.get("adj_factor", ""),
                        row.get("is_suspended", "false"),
                        row.get("is_st", "false"),
                        row.get("is_limit_up", "false"),
                        row.get("is_limit_down", "false"),
                        row.get("data_source", "sina"),
                    ),
                )
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO int_company_stats (
                        ts_code, trade_date, total_mv, circ_mv, pe_ttm, pb,
                        turnover_rate, volume_ratio, daily_return,
                        trailing_return_5d, trailing_return_20d, trailing_return_60d,
                        volatility_5d, volatility_20d, volatility_60d, up_days_20d,
                        forward_return_1d, forward_return_3d, forward_return_5d, data_source
                    )
                    VALUES (
                        %s, %s, NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric,
                        NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric,
                        NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric,
                        NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric, NULLIF(%s, '')::int,
                        NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric, %s
                    )
                    ON CONFLICT (ts_code, trade_date) DO UPDATE
                    SET
                        total_mv = EXCLUDED.total_mv,
                        circ_mv = EXCLUDED.circ_mv,
                        pe_ttm = EXCLUDED.pe_ttm,
                        pb = EXCLUDED.pb,
                        turnover_rate = EXCLUDED.turnover_rate,
                        volume_ratio = EXCLUDED.volume_ratio,
                        daily_return = EXCLUDED.daily_return,
                        trailing_return_5d = EXCLUDED.trailing_return_5d,
                        trailing_return_20d = EXCLUDED.trailing_return_20d,
                        trailing_return_60d = EXCLUDED.trailing_return_60d,
                        volatility_5d = EXCLUDED.volatility_5d,
                        volatility_20d = EXCLUDED.volatility_20d,
                        volatility_60d = EXCLUDED.volatility_60d,
                        up_days_20d = EXCLUDED.up_days_20d,
                        forward_return_1d = EXCLUDED.forward_return_1d,
                        forward_return_3d = EXCLUDED.forward_return_3d,
                        forward_return_5d = EXCLUDED.forward_return_5d,
                        data_source = EXCLUDED.data_source,
                        updated_at = NOW()
                    """,
                    (
                        row["ts_code"],
                        row["trade_date"],
                        row.get("total_mv", ""),
                        row.get("circ_mv", ""),
                        row.get("pe_ttm", ""),
                        row.get("pb", ""),
                        row.get("turnover_rate", ""),
                        row.get("volume_ratio", ""),
                        row.get("daily_return", ""),
                        row.get("trailing_return_5d", ""),
                        row.get("trailing_return_20d", ""),
                        row.get("trailing_return_60d", ""),
                        row.get("volatility_5d", ""),
                        row.get("volatility_20d", ""),
                        row.get("volatility_60d", ""),
                        row.get("up_days_20d", ""),
                        row.get("forward_return_1d", ""),
                        row.get("forward_return_3d", ""),
                        row.get("forward_return_5d", ""),
                        row.get("data_source", "tushare"),
                    ),
                )
        conn.commit()
    print(f"Loaded {len(quote_rows)} stock_daily_quotes rows into {args.db}")
    print(f"Loaded {len(rows)} company stats into {args.db}")


if __name__ == "__main__":
    main()
