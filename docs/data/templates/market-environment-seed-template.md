# 市场环境 Seed 模板

当你需要给 `market_environment_daily` 回填 `northbound_net_flow` 或替换基准信息时，
可准备一个 seed CSV，并通过下面的命令加载：

```bash
python3 src/cli/linking.py load-market-environment --db stock_event_mining --input output/seeds/market_environment_seed.csv
```

## 建议列名

```text
trade_date,benchmark_code,benchmark_name,northbound_net_flow
```

## 示例

```csv
trade_date,benchmark_code,benchmark_name,northbound_net_flow
2026-04-14,000300.SH,沪深300,4523000000
2026-04-15,000300.SH,沪深300,-1180000000
```

## 字段说明

- `trade_date`: 必填，支持 `YYYY-MM-DD`。
- `benchmark_code`: 可选，默认 `000300.SH`。
- `benchmark_name`: 可选，默认 `沪深300`。
- `northbound_net_flow`: 可选，建议填净流入金额，单位由你们内部统一口径决定。

## 加载行为

- `load-market-environment` 会先基于 `stock_daily_quotes` 生成基础市场环境。
- 如果 seed 中某日存在 `northbound_net_flow`、`benchmark_code`、`benchmark_name`，则覆盖基础生成结果。
- 若不传 `--input`，加载器会自动尝试读取：
  - `output/seeds/market_environment_seed.csv`

## 当前基础字段来源

即使不传 seed，加载器也会继续基于 `stock_daily_quotes` 自动生成：

- `index_return_1d`
- `index_return_5d`
- `index_volatility_20d`
- `market_turnover`
- `up_count`
- `down_count`
- `limit_up_count`
- `limit_down_count`
- `sector_hotness`
- `risk_on_off_score`

当 `stock_daily_quotes.amount` 存在时，`market_turnover` 优先使用真实成交额；否则回退到 `volume * close` 代理值。
