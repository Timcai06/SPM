# company_profiles seed 模板

当你希望给 `company_profiles` 补充上市日期、地区、国企标签、员工、股本等字段时，
可准备一个 CSV，并通过下面的命令加载：

```bash
python3 src/cli/linking.py load-company-profiles --db stock_event_mining --input output/seeds/company_profiles_seed.csv
```

## 建议列名

```text
ts_code,company_name,exchange,industry_l1,industry_l2,business_scope,core_products,concept_tags,region,list_date,state_owned_flag,company_type,employees,total_shares,float_shares,main_customers,main_suppliers
```

## 示例行

```csv
ts_code,company_name,exchange,industry_l1,industry_l2,business_scope,core_products,concept_tags,region,list_date,state_owned_flag,company_type,employees,total_shares,float_shares,main_customers,main_suppliers
000001.SZ,平安银行,SZSE,金融,银行,商业银行及相关金融服务,"[""零售银行"",""对公金融""]","[""金融"",""银行""]",广东-深圳,1991-04-03,false,主板,41000,19405918198,19405918198,"[""零售客户"",""企业客户""]","[""同业资金"",""存款客户""]"
```

## 字段说明

- `ts_code`: 必填，需与 `companies.ts_code` 对齐。
- `region`: 推荐使用 `省份-城市`。
- `list_date`: 支持 `YYYY-MM-DD` 或 `YYYYMMDD`。
- `state_owned_flag`: 支持 `true/false`、`1/0`、`是/否`、`国企/民企`。
- `core_products` / `concept_tags` / `main_customers` / `main_suppliers`: 推荐写成 JSON 数组。
- `employees` / `total_shares` / `float_shares`: 数值列，可为空。

## 加载行为

- `load-company-profiles` 会先读取 `companies` 作为基础维度。
- 如果 seed 里存在同名字段，则优先用 seed 覆盖。
- 若未显式传 `--input`，加载器会自动尝试：
  - `output/seeds/company_profiles_seed.csv`
  - `output/seeds/companies_a_share.csv`
  - `output/seeds/companies_public.csv`
  - `output/seeds/companies_seed.csv`
