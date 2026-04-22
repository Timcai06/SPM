# company_relations seed 模板

当你需要给 `company_relations` 补充供应链、持股、同实控人、同概念等关系边时，
可准备一个 seed CSV，并通过下面的命令加载：

```bash
python3 src/cli/graph.py load-relations --db stock_event_mining --input output/seeds/company_relations_seed.csv
```

## 建议列名

```text
source_ts_code,target_ts_code,source_company_name,target_company_name,relation_type,relation_strength,direction,evidence_note,data_source,confidence,effective_date,expiry_date,relation_group,same_controller_flag,same_industry_flag,same_concept_flag
```

## 最小示例

```csv
source_ts_code,target_ts_code,relation_type,relation_strength,direction,evidence_note
000028.SZ,000598.SZ,供应链,0.72,directed,来自年报披露的客户/供应商关系
```

## 扩展示例

```csv
source_ts_code,target_ts_code,source_company_name,target_company_name,relation_type,relation_strength,direction,evidence_note,data_source,confidence,effective_date,expiry_date,relation_group,same_controller_flag,same_industry_flag,same_concept_flag
000028.SZ,000598.SZ,国药一致,兴蓉环境,供应链,0.72,directed,来自年报披露的客户/供应商关系,annual_report,high,2025-01-01,,产业链,false,false,false
000028.SZ,000669.SZ,国药一致,ST金鸿,同概念,0.35,undirected,同属某主题概念板块,manual,medium,2025-01-01,,主题联动,false,false,true
```

## 字段说明

- `source_ts_code` / `target_ts_code`: 推荐优先填写。
- `source_company_name` / `target_company_name`: 当 `ts_code` 缺失时，可作为精确名称匹配回退。
- `relation_type`: 必填，例如 `供应链 / 持股关系 / 同一实控人 / 同概念 / 同行业`。
- `relation_strength`: 建议 `0~1`。
- `direction`: `directed` 或 `undirected`。
- `evidence_note`: 建议写明证据来源。
- `data_source` / `confidence` / `effective_date` / `expiry_date` / `relation_group`: 会写入 `evidence` JSON。
- `same_controller_flag` / `same_industry_flag` / `same_concept_flag`: 会写入 `evidence` JSON。

## 加载行为

- 导入器会先删除旧的 `is_manual_override = TRUE` 的人工边，再写入新的 seed 结果。
- 对 `undirected` 边，会自动按公司 ID 归一化顺序，避免重复。
- 若 `relation_strength` 不合法，会回落到 `0.5000`。
- 若 `relation_type` 为空，记录会被跳过。
