# 无 Tushare 执行路线

当本机没有 `TUSHARE_TOKEN`，或你不准备依赖 Tushare 时，当前仓库推荐走下面这条混合路线：

- 公司基础/画像：公共源 + seed CSV
- 个股日行情/统计：优先 `auto`（Tushare 不可用时自动回退到 AKShare，再回退到 Sina）
- 如果你手里已有终端导出的本地行情 CSV，可直接走 `local CSV -> load-company-stats`
- 市场环境：`stock_daily_quotes` 自动生成 + seed 覆盖北向资金
- 公司关系边：seed CSV

## 1. 公司基础与画像

### 1.1 用公共源生成公司 seed

```bash
python3 src/cli/task2.py import-companies-public --output output/seeds/companies_public.csv
python3 src/cli/task2.py load-companies --db stock_event_mining --input output/seeds/companies_public.csv
```

### 1.2 导入公司画像快照

如果你有更完整的画像 CSV：

```bash
python3 src/cli/task2.py load-company-profiles --db stock_event_mining --input output/seeds/company_profiles_seed.csv
```

如果没有，加载器会自动尝试：

- `output/seeds/company_profiles_seed.csv`
- `output/seeds/companies_a_share.csv`
- `output/seeds/companies_public.csv`
- `output/seeds/companies_seed.csv`

模板参考：
- `docs/company_profiles_seed_template.md`

## 2. 生成公司统计特征 + 正式行情表

```bash
python3 src/cli/task2.py import-company-stats --db stock_event_mining --source auto --days 120 --max-symbols 300
python3 src/cli/task2.py load-company-stats --db stock_event_mining
```

这一步现在会按下面顺序尝试：

1. Tushare
2. AKShare
3. Sina

并同时生成：

- `output/seeds/company_stats.csv`
- `output/seeds/stock_daily_quotes.csv`

随后写入：

- `int_company_stats`
- `stock_daily_quotes`

## 3. 生成市场环境日表

无 seed 时：

```bash
python3 src/cli/task2.py load-market-environment --db stock_event_mining
```

如果你另外整理了北向资金或基准信息：

```bash
python3 src/cli/task2.py load-market-environment --db stock_event_mining --input output/seeds/market_environment_seed.csv
```

模板参考：
- `docs/market_environment_seed_template.md`

## 4. 导入公司关系边

```bash
python3 src/cli/task3.py load-relations --db stock_event_mining --input output/seeds/company_relations_seed.csv
python3 src/cli/task3.py propagate --db stock_event_mining
```

模板参考：
- `docs/company_relations_seed_template.md`

## 5. 回归样本链路

```bash
python3 src/cli/task2.py link-events --db stock_event_mining --top-k 3 --min-score 0.35
python3 src/cli/task1.py train-samples --db stock_event_mining --min-link-score 0.35 --label-dataset output/task1_event_return_dataset.csv
```

## 6. 推荐执行顺序

```bash
python3 src/cli/task2.py import-companies-public --output output/seeds/companies_public.csv
python3 src/cli/task2.py load-companies --db stock_event_mining --input output/seeds/companies_public.csv
python3 src/cli/task2.py load-company-profiles --db stock_event_mining --input output/seeds/company_profiles_seed.csv
python3 src/cli/task2.py import-company-stats --db stock_event_mining --source akshare --days 120 --max-symbols 300
python3 src/cli/task2.py load-company-stats --db stock_event_mining
python3 src/cli/task2.py load-market-environment --db stock_event_mining --input output/seeds/market_environment_seed.csv
python3 src/cli/task3.py load-relations --db stock_event_mining --input output/seeds/company_relations_seed.csv
python3 src/cli/task3.py propagate --db stock_event_mining
python3 src/cli/task1.py train-samples --db stock_event_mining --min-link-score 0.35 --label-dataset output/task1_event_return_dataset.csv
```

## 7. 当前已知限制

- AKShare 路线可以补齐较完整的 `stock_daily_quotes`，但 `adj_factor` 目前仍为空。
- `northbound_net_flow` 仍建议用外部 seed CSV 补入。
- `state_owned_flag` 仍主要依赖画像 seed / 手工补录。
- `company_relations` 的质量仍取决于你的 seed 质量，而不是自动抽边。
如果你明确想只走 Sina，可用：

```bash
python3 src/cli/task2.py import-company-stats --db stock_event_mining --source sina --days 120 --max-symbols 300
```

如果你明确想只走 AKShare，可用：

```bash
python3 src/cli/task2.py import-company-stats --db stock_event_mining --source akshare --days 120 --max-symbols 300
```

但 AKShare 上游偶尔会拒绝请求，因此在无 token 环境下，`source auto` 往往更稳。

### 2.1 如果你已有本地行情 CSV

```bash
python3 src/cli/task2.py import-company-stats-local --input docs/local_market_prices_template.csv
python3 src/cli/task2.py load-company-stats --db stock_event_mining
```

这条路线现在也会同时生成：

- `output/seeds/company_stats.csv`
- `output/seeds/stock_daily_quotes.csv`

模板参考：
- `docs/local_market_prices_template.csv`

注意：
- 本地 CSV 里的 `ts_code` 必须已经存在于 `companies` 表，否则 `load-company-stats` 会触发外键错误。
