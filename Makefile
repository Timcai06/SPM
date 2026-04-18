PY ?= /opt/homebrew/bin/python3
DB ?= stock_event_mining
LIMIT ?= 20
TOP_K ?= 3
MIN_SCORE ?= 0.35
TIME_BUDGET ?= 180
MAX_ROWS ?= 200
API_TIMEOUT ?= 10
PROGRESS_EVERY ?= 5
LINK_PROGRESS_EVERY ?= 250
TOKEN_FILE ?= .secrets/tushare_token.txt
USE_TUSHARE ?= 0
STATS_SOURCE ?= sina
DAYS ?= 120
STATS_MAX_SYMBOLS ?= 800
STATS_MAX_ROWS ?= 1200
NEG_MAX_PER_DAY ?= 100
BACKFILL_ROUNDS ?= 3
BACKFILL_LIMIT ?= 60
BACKFILL_MAX_ROWS ?= 300
BACKFILL_DAYS ?= 120
BACKFILL_STATS_MAX_SYMBOLS ?= 200
HISTORY_SOURCE ?= cninfo-disclosure
HISTORY_SYMBOL_SOURCE ?= db
HISTORY_START ?= 2023-01-01
HISTORY_END ?= 2025-12-31
HISTORY_MAX_SYMBOLS ?= 200
HISTORY_OFFSET ?= 0
HISTORY_LIMIT_PER_SYMBOL ?= 100
HISTORY_WORKERS ?= 4
HISTORY_RETRIES ?= 2
HISTORY_SLEEP ?= 0.1
CLASSIFY_BATCH_SIZE ?= 3000
CLASSIFY_MAX_BATCHES ?= 20
RECLASSIFY_SOURCE ?= 巨潮资讯网/历史公告
RECLASSIFY_BATCH_SIZE ?= 5000
RECLASSIFY_MAX_BATCHES ?= 10
INDUSTRY_MAX ?= 100
INDUSTRY_OFFSET ?= 0
INDUSTRY_SLEEP ?= 0.05
STANDARD_INDUSTRY_MAX ?= 200
STANDARD_INDUSTRY_OFFSET ?= 0
STANDARD_INDUSTRY_SLEEP ?= 0.05
STANDARD_INDUSTRY_START ?= 19900101
STANDARD_INDUSTRY_END ?= 20251231
STANDARD_INDUSTRY_RETRIES ?= 2
STANDARD_INDUSTRY_BACKOFF ?= 0.8
STANDARD_INDUSTRY_ONLY_DIRTY ?=
STANDARD_INDUSTRY_SKIP_LEGACY ?=
DELIVERY_DIR ?= output/delivery
MAX_EXPORT_MB ?= 400

FEATURE_TOKEN_ARG :=
ifeq ($(USE_TUSHARE),1)
FEATURE_TOKEN_ARG := --tushare-token-file $(TOKEN_FILE)
else
FEATURE_TOKEN_ARG := --disable-tushare
endif

.PHONY: help \
	companies-all standard-industries industries history classify-pending reclassify-source relink core-status core-pipeline \
	cluster-stats backfill-structured-features export-yearly check-export-size \
	collect link feature train status qa stats-import stats-load negatives \
	profiles \
	market-env \
	sentiment \
	delivery-status \
	full full-with-stats backfill \
	text market llm trial \
	go r q c l f t s qa ds si sl n bf

help:
	@echo "推荐入口："
	@echo "  make core-pipeline       # 四张核心表流水线：采历史 -> 分类 -> 链接 -> 状态"
	@echo "  make companies-all       # 扩 companies 到全A公司池"
	@echo "  make standard-industries # 补 companies 一级标准行业（CNInfo/证监会口径）"
	@echo "  make industries          # 补 companies 二级行业/概念标签（东方财富板块）"
	@echo "  make history             # 历史采集 raw_documents（默认巨潮公告）"
	@echo "  make classify-pending    # 分类未处理 raw_documents"
	@echo "  make reclassify-source   # 重跑某个来源的分类规则"
	@echo "  make relink              # 重跑 event_company_links，带进度"
	@echo "  make cluster-stats       # 回填事件簇统计特征（报道量/分歧度等）"
	@echo "  make backfill-structured-features # 回填结构化事件新增特征列"
	@echo "  make export-yearly       # 按年导出 structured_events / event_company_links"
	@echo "  make core-status         # 查看四张核心表规模与质量摘要"
	@echo ""
	@echo "常用参数："
	@echo "  make history HISTORY_SOURCE=akshare-news HISTORY_MAX_SYMBOLS=1000 HISTORY_OFFSET=0 HISTORY_LIMIT_PER_SYMBOL=20 HISTORY_WORKERS=12"
	@echo "  make standard-industries STANDARD_INDUSTRY_MAX=200 STANDARD_INDUSTRY_OFFSET=0"
	@echo "  make industries INDUSTRY_MAX=100 INDUSTRY_OFFSET=100"
	@echo "  make reclassify-source RECLASSIFY_SOURCE='巨潮资讯网/历史公告'"
	@echo ""
	@echo "旧目标仍可用：collect link feature train status qa delivery-status stats-import stats-load market-env sentiment"
	@echo ""
	@echo "短别名：s=status ds=delivery-status l=relink"

companies-all:
	$(PY) src/cli/task2.py import-companies-all-a --db $(DB)

standard-industries:
	$(PY) src/cli/task2.py import-company-standard-industries \
		--db $(DB) \
		--max-symbols $(STANDARD_INDUSTRY_MAX) \
		--offset $(STANDARD_INDUSTRY_OFFSET) \
		--start-date $(STANDARD_INDUSTRY_START) \
		--end-date $(STANDARD_INDUSTRY_END) \
		--sleep-sec $(STANDARD_INDUSTRY_SLEEP) \
		--retries $(STANDARD_INDUSTRY_RETRIES) \
		--failure-backoff-sec $(STANDARD_INDUSTRY_BACKOFF) \
		--progress-every 20 \
		$(STANDARD_INDUSTRY_ONLY_DIRTY) \
		$(STANDARD_INDUSTRY_SKIP_LEGACY)

industries:
	$(PY) src/cli/task2.py import-company-industries \
		--db $(DB) \
		--max-industries $(INDUSTRY_MAX) \
		--offset $(INDUSTRY_OFFSET) \
		--sleep-sec $(INDUSTRY_SLEEP) \
		--progress-every 20

history:
	$(PY) src/cli/task1.py collect-history \
		--db $(DB) \
		--source $(HISTORY_SOURCE) \
		--symbol-source $(HISTORY_SYMBOL_SOURCE) \
		--start-date $(HISTORY_START) \
		--end-date $(HISTORY_END) \
		--max-symbols $(HISTORY_MAX_SYMBOLS) \
		--offset $(HISTORY_OFFSET) \
		--limit-per-symbol $(HISTORY_LIMIT_PER_SYMBOL) \
		--workers $(HISTORY_WORKERS) \
		--retries $(HISTORY_RETRIES) \
		--sleep-sec $(HISTORY_SLEEP)

classify-pending:
	$(PY) src/cli/task1.py classify-pending \
		--db $(DB) \
		--batch-size $(CLASSIFY_BATCH_SIZE) \
		--max-batches $(CLASSIFY_MAX_BATCHES)

reclassify-source:
	$(PY) src/cli/task1.py reclassify-source \
		--db $(DB) \
		--source '$(RECLASSIFY_SOURCE)' \
		--batch-size $(RECLASSIFY_BATCH_SIZE) \
		--max-batches $(RECLASSIFY_MAX_BATCHES)

relink:
	$(PY) src/cli/task2.py link-events \
		--db $(DB) \
		--top-k $(TOP_K) \
		--min-score $(MIN_SCORE) \
		--progress-every $(LINK_PROGRESS_EVERY)

cluster-stats:
	$(PY) src/capabilities/jobs/events/cluster_stats_job.py --db $(DB)

backfill-structured-features:
	$(PY) src/capabilities/jobs/events/backfill_structured_features_job.py --db $(DB) --batch-size 5000 --max-batches 0

export-yearly:
	mkdir -p $(DELIVERY_DIR)
	psql -d $(DB) -c "\copy (select * from structured_events where event_date >= date '2023-01-01' and event_date < date '2024-01-01') to '$(DELIVERY_DIR)/structured_events_2023.csv' csv header"
	psql -d $(DB) -c "\copy (select * from structured_events where event_date >= date '2024-01-01' and event_date < date '2025-01-01') to '$(DELIVERY_DIR)/structured_events_2024.csv' csv header"
	psql -d $(DB) -c "\copy (select * from structured_events where event_date >= date '2025-01-01' and event_date < date '2026-01-01') to '$(DELIVERY_DIR)/structured_events_2025.csv' csv header"
	psql -d $(DB) -c "\copy (select l.* from event_company_links l join structured_events se on se.id=l.structured_event_id where se.event_date >= date '2023-01-01' and se.event_date < date '2024-01-01') to '$(DELIVERY_DIR)/event_company_links_2023.csv' csv header"
	psql -d $(DB) -c "\copy (select l.* from event_company_links l join structured_events se on se.id=l.structured_event_id where se.event_date >= date '2024-01-01' and se.event_date < date '2025-01-01') to '$(DELIVERY_DIR)/event_company_links_2024.csv' csv header"
	psql -d $(DB) -c "\copy (select l.* from event_company_links l join structured_events se on se.id=l.structured_event_id where se.event_date >= date '2025-01-01' and se.event_date < date '2026-01-01') to '$(DELIVERY_DIR)/event_company_links_2025.csv' csv header"
	$(MAKE) check-export-size

check-export-size:
	@echo "[check-export-size] max_mb=$(MAX_EXPORT_MB)"
	@for f in $(DELIVERY_DIR)/*.csv; do \
		bytes=$$(wc -c < $$f); \
		mb=$$((bytes / 1024 / 1024)); \
		echo "$$f => $${mb}MB"; \
		if [ $$mb -gt $(MAX_EXPORT_MB) ]; then \
			echo "ERROR: $$f exceeds $(MAX_EXPORT_MB)MB"; \
			exit 1; \
		fi; \
	done

core-status:
	psql -d $(DB) -c "select 'companies' as table_name, count(*) as rows from companies union all select 'raw_documents', count(*) from raw_documents union all select 'structured_events', count(*) from structured_events union all select 'event_company_links', count(*) from event_company_links order by table_name;"
	psql -d $(DB) -c "select count(*) as events, count(*) filter (where event_subject_subtype='未细分') as unrefined_subtype, count(*) filter (where subject_entities='[]'::jsonb) as empty_entities from structured_events;"
	psql -d $(DB) -c "select count(*) as links, count(distinct structured_event_id) as linked_events, count(distinct company_id) as linked_companies, count(*) filter (where link_type='direct_match') as direct_links, count(*) filter (where link_type='industry_match') as industry_links, round(avg(final_link_score)::numeric, 4) as avg_score from event_company_links;"

core-pipeline: history classify-pending relink core-status

collect:
	$(PY) src/cli/task1.py run --limit $(LIMIT) --skip-validate --db $(DB)

link: relink

feature:
	$(PY) src/cli/task1.py feature --db $(DB) --analysis-mode event-study --benchmark hs300 --event-windows 1,3,5 --time-budget-sec $(TIME_BUDGET) --max-rows $(MAX_ROWS) --api-timeout-sec $(API_TIMEOUT) --progress-every $(PROGRESS_EVERY) $(FEATURE_TOKEN_ARG)

train:
	$(PY) src/cli/task1.py train-samples \
		--db $(DB) \
		--min-link-score $(MIN_SCORE) \
		--label-dataset output/task1_event_return_dataset.csv

status:
	$(PY) src/cli/task1.py db-status --db $(DB)

qa:
	$(PY) src/cli/task1.py qa --db $(DB)

delivery-status:
	$(PY) src/cli/task1.py delivery-status --db $(DB)

stats-import:
	$(PY) src/cli/task2.py import-company-stats --db $(DB) --source $(STATS_SOURCE) --days $(DAYS) --max-symbols $(STATS_MAX_SYMBOLS) --max-rows $(STATS_MAX_ROWS) --tushare-token-file $(TOKEN_FILE)

stats-load:
	$(PY) src/cli/task2.py load-company-stats --db $(DB)

negatives:
	$(PY) src/cli/task2.py build-negative-samples --db $(DB) --max-per-day $(NEG_MAX_PER_DAY)

full: collect link sentiment feature train status

full-with-stats: full stats-import stats-load profiles market-env negatives status

text: full

profiles-import:
	$(PY) src/cli/task2.py import-company-profiles --db $(DB)

profiles:
	$(PY) src/cli/task2.py load-company-profiles --db $(DB)

market-env:
	$(PY) src/cli/task2.py load-market-environment --db $(DB)

sentiment:
	$(PY) src/cli/task2.py load-sentiment-propagation --db $(DB)

market: stats-import stats-load profiles market-env sentiment qa

llm:
	$(PY) src/cli/task1.py classify --db $(DB) --use-llm --llm-max-rows 10 --skip-db-load

trial: full stats-import stats-load profiles market-env qa

backfill:
	@echo "[backfill] rounds=$(BACKFILL_ROUNDS), limit=$(BACKFILL_LIMIT), max_rows=$(BACKFILL_MAX_ROWS)"
	@i=1; while [ $$i -le $(BACKFILL_ROUNDS) ]; do \
		echo "[backfill] round $$i/$(BACKFILL_ROUNDS)"; \
		$(PY) src/cli/task1.py run --limit $(BACKFILL_LIMIT) --skip-validate --db $(DB); \
		i=$$((i+1)); \
	done
	$(PY) src/cli/task2.py run --db $(DB) --top-k $(TOP_K) --min-score $(MIN_SCORE)
	$(PY) src/cli/task1.py feature --db $(DB) --analysis-mode event-study --benchmark hs300 --event-windows 1,3,5 --time-budget-sec $(TIME_BUDGET) --max-rows $(BACKFILL_MAX_ROWS) --api-timeout-sec $(API_TIMEOUT) --progress-every $(PROGRESS_EVERY) $(FEATURE_TOKEN_ARG)
	$(PY) src/cli/task1.py train-samples --db $(DB) --min-link-score $(MIN_SCORE) --label-dataset output/task1_event_return_dataset.csv
	$(PY) src/cli/task2.py import-company-stats --db $(DB) --source $(STATS_SOURCE) --days $(BACKFILL_DAYS) --max-symbols $(BACKFILL_STATS_MAX_SYMBOLS) --max-rows $(STATS_MAX_ROWS) --tushare-token-file $(TOKEN_FILE)
	$(PY) src/cli/task2.py load-company-stats --db $(DB)
	$(PY) src/cli/task2.py build-negative-samples --db $(DB) --max-per-day $(NEG_MAX_PER_DAY)
	$(PY) src/cli/task2.py load-sentiment-propagation --db $(DB)
	$(PY) src/cli/task1.py qa --db $(DB)

# Short aliases
go: full
r: full-with-stats
q: collect status
c: collect
l: link
f: feature
t: train
s: status
ds: delivery-status
si: stats-import
sl: stats-load
n: negatives
bf: backfill
