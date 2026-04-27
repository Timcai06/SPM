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
HISTORY_CNINFO_FULLTEXT ?= 0
HISTORY_CNINFO_FULLTEXT_MAX_CHARS ?= 12000
HISTORY_DB_FLUSH_EVERY ?= 100
HISTORY_MAX_PAGES ?= 20
HISTORY_PAGE_SIZE ?= 50
HISTORY_QUALITY_BODY_ONLY ?= 0
HISTORY_MIN_CONTENT_LENGTH ?= 300
CNINFO_BACKFILL_SOURCE ?= 巨潮资讯网/历史公告
CNINFO_BACKFILL_START ?= 2025-01-01
CNINFO_BACKFILL_END ?= 2026-01-01
CNINFO_BACKFILL_MAX_ROWS ?= 5000
CNINFO_BACKFILL_OFFSET ?= 0
CNINFO_BACKFILL_ID_MIN ?= 0
CNINFO_BACKFILL_ID_MAX ?= 0
CNINFO_BACKFILL_SHARD_COUNT ?= 0
CNINFO_BACKFILL_SHARD_INDEX ?= 0
CNINFO_BACKFILL_WORKERS ?= 8
CNINFO_BACKFILL_RETRIES ?= 3
CNINFO_BACKFILL_SLEEP ?= 0.02
CNINFO_BACKFILL_PROGRESS_EVERY ?= 10
CNINFO_BACKFILL_HEARTBEAT_SEC ?= 5
CNINFO_BACKFILL_DETAIL_TIMEOUT_SEC ?= 20
CNINFO_BACKFILL_PDF_TIMEOUT_SEC ?= 20
CNINFO_BACKFILL_DB_FLUSH_EVERY ?= 100
CNINFO_BACKFILL_MAX_CHARS ?= 12000
CLASSIFY_BATCH_SIZE ?= 3000
CLASSIFY_MAX_BATCHES ?= 20
RECLASSIFY_SOURCE ?= 巨潮资讯网/历史公告
RECLASSIFY_BATCH_SIZE ?= 5000
RECLASSIFY_MAX_BATCHES ?= 10
EVENT_START ?=
EVENT_END ?=
EVENT_ONLY_NEEDY ?= 0
EVENT_LLM ?= 0
EVENT_LOCAL_LLM_ONLY ?= 0
EVENT_LLM_MAX_ROWS ?= 100
EVENT_LLM_CONFIDENCE_THRESHOLD ?= 0.70
EVENT_LLM_PROGRESS_EVERY ?= 10
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
RAW_AUDIT_START ?= 2025-01-01
RAW_AUDIT_END ?= 2027-01-01
RAW_AUDIT_TOP_N ?= 200
RAW_REFRESH_START ?= 2025-01-01
RAW_REFRESH_END ?= 2026-04-23
RAW_REFRESH_TARGET_BODY_ROWS ?= 2000
RAW_REFRESH_MAX_JOBS ?= 6
RAW_REFRESH_MIN_CONTENT_LENGTH ?= 300
RAW_REFRESH_CNINFO_MAX_SYMBOLS ?= 3000
RAW_REFRESH_CNINFO_LIMIT_PER_SYMBOL ?= 120
RAW_REFRESH_CNINFO_WORKERS ?= 32
RAW_REFRESH_CNINFO_BACKFILL_ROWS ?= 30000
RAW_REFRESH_CNINFO_BACKFILL_WORKERS ?= 32
RAW_REFRESH_FORCE ?= 0

FEATURE_TOKEN_ARG :=
ifeq ($(USE_TUSHARE),1)
FEATURE_TOKEN_ARG := --tushare-token-file $(TOKEN_FILE)
else
FEATURE_TOKEN_ARG := --disable-tushare
endif

.PHONY: help \
	company-universe standard-industries board-industries \
	collect-live collect-history backfill-cninfo-fulltext \
	events-run classify-pending reclassify-source \
	linking-run link-events \
	graph-run load-relations propagate \
	cluster-stats backfill-event-features refresh-event-features export-yearly check-export-size \
	db-summary db-storage-audit db-raw-source-audit db-normalize-raw-categories db-stage-clean research-base-pipeline \
	db-raw-audit ingest-full-raw \
	research-feature research-train-samples research-negative-samples \
	stats-import stats-load profiles-import profiles-load market-env sentiment-load \
	quality-check quality-sample quality-summary delivery-status \
	full full-with-market llm trial go

help:
	@echo "推荐入口："
	@echo "  ./SPM ingest full DB=stock_event_mining             # 一键做 2025/2026 全量补数据"
	@echo "  ./SPM status raw DB=stock_event_mining              # 看 raw 层覆盖、正文质量、目标差距"
	@echo "  ./SPM status clean-stage DB=stock_event_mining --yes   # 清理可重建 stage 表"
	@echo ""
	@echo "工程入口："
	@echo "  make research-base-pipeline # 历史采集 -> 分类 -> 链接 -> 数据库摘要"
	@echo "  make company-universe       # 扩 companies 到全A公司池"
	@echo "  make standard-industries    # 补 companies 一级标准行业（CNInfo/证监会口径）"
	@echo "  make board-industries       # 补 companies 二级行业/概念标签（东方财富板块）"
	@echo "  make collect-history        # 历史采集 raw_documents（默认巨潮公告）"
	@echo "  make backfill-cninfo-fulltext # 用已有 raw_documents URL 回填巨潮正文"
	@echo "  make events-run             # 实时采集 -> 事件标准化 -> 归并 -> 校验"
	@echo "  make classify-pending       # 分类未处理 raw_documents"
	@echo "  make reclassify-source      # 重跑某个来源的分类规则"
	@echo "  make link-events            # 生成 event_company_links"
	@echo "  make graph-run              # 导入公司关系并构建传播链接"
	@echo "  make research-feature       # 事件研究 / 收益标签"
	@echo "  make research-train-samples # 生成 event_research_samples"
	@echo "  make research-negative-samples # 生成非事件负样本"
	@echo "  make quality-summary        # 数据库质量摘要"
	@echo "  make db-raw-source-audit    # 2025/2026 各 raw 来源数量与正文覆盖"
	@echo "  make db-normalize-raw-categories # 统一 raw_documents.symbol_or_subject 到附件 2 四类"
	@echo "  make ingest-full-raw        # 一键做 2025/2026 全量补数据：补来源、补正文、补回填"
	@echo "  make db-raw-audit           # 查看 raw 层覆盖、正文质量、目标差距"
	@echo "  make db-stage-clean DB=stock_event_mining YES=1     # 底层 make 入口"
	@echo "  说明：采集相关命令默认在进程内临时清除代理环境变量，不影响系统全局网络设置"
	@echo ""
	@echo "常用参数："
	@echo "  make collect-history HISTORY_SOURCE=akshare-news HISTORY_MAX_SYMBOLS=1000 HISTORY_OFFSET=0 HISTORY_LIMIT_PER_SYMBOL=20 HISTORY_WORKERS=12"
	@echo "  make collect-history HISTORY_SOURCE=cninfo-disclosure HISTORY_CNINFO_FULLTEXT=1 HISTORY_CNINFO_FULLTEXT_MAX_CHARS=12000"
	@echo "  make collect-history HISTORY_SOURCE=gov-news HISTORY_START=2025-01-01 HISTORY_END=2026-04-23 HISTORY_MAX_PAGES=100 HISTORY_PAGE_SIZE=50 HISTORY_QUALITY_BODY_ONLY=1 HISTORY_MIN_CONTENT_LENGTH=300"
	@echo "  make ingest-full-raw DB=stock_event_mining"
	@echo "  make backfill-cninfo-fulltext CNINFO_BACKFILL_START=2025-01-01 CNINFO_BACKFILL_END=2026-01-01 CNINFO_BACKFILL_MAX_ROWS=5000 CNINFO_BACKFILL_OFFSET=0"
	@echo "  make backfill-cninfo-fulltext CNINFO_BACKFILL_SHARD_COUNT=2 CNINFO_BACKFILL_SHARD_INDEX=0 CNINFO_BACKFILL_WORKERS=4"
	@echo "  make backfill-cninfo-fulltext CNINFO_BACKFILL_PROGRESS_EVERY=10 CNINFO_BACKFILL_HEARTBEAT_SEC=5 CNINFO_BACKFILL_DETAIL_TIMEOUT_SEC=12 CNINFO_BACKFILL_PDF_TIMEOUT_SEC=18"
	@echo "  make standard-industries STANDARD_INDUSTRY_MAX=200 STANDARD_INDUSTRY_OFFSET=0"
	@echo "  make board-industries INDUSTRY_MAX=100 INDUSTRY_OFFSET=100"
	@echo "  make reclassify-source RECLASSIFY_SOURCE='巨潮资讯网/历史公告'"
	@echo ""
	@echo "常用组合：full full-with-market trial go"

company-universe:
	$(PY) src/cli/linking.py import-companies-all-a --db $(DB)

standard-industries:
	$(PY) src/cli/linking.py import-company-standard-industries \
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

board-industries:
	$(PY) src/cli/linking.py import-company-industries \
		--db $(DB) \
		--max-industries $(INDUSTRY_MAX) \
		--offset $(INDUSTRY_OFFSET) \
		--sleep-sec $(INDUSTRY_SLEEP) \
		--progress-every 20

collect-live:
	$(PY) src/cli/collect.py collect --limit $(LIMIT)

collect-history:
	$(PY) src/cli/collect.py collect-history \
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
		--sleep-sec $(HISTORY_SLEEP) \
		--db-flush-every $(HISTORY_DB_FLUSH_EVERY) \
		--max-pages $(HISTORY_MAX_PAGES) \
		--page-size $(HISTORY_PAGE_SIZE) \
		$(if $(filter 1,$(HISTORY_QUALITY_BODY_ONLY)),--quality-body-only,) \
		--min-content-length $(HISTORY_MIN_CONTENT_LENGTH) \
		$(if $(filter 1,$(HISTORY_CNINFO_FULLTEXT)),--cninfo-fulltext,) \
		--cninfo-fulltext-max-chars $(HISTORY_CNINFO_FULLTEXT_MAX_CHARS)

backfill-cninfo-fulltext:
	$(PY) src/cli/collect.py backfill-cninfo-fulltext \
		--db $(DB) \
		--source '$(CNINFO_BACKFILL_SOURCE)' \
		--start-date $(CNINFO_BACKFILL_START) \
		--end-date $(CNINFO_BACKFILL_END) \
		--max-rows $(CNINFO_BACKFILL_MAX_ROWS) \
		--offset $(CNINFO_BACKFILL_OFFSET) \
		--id-min $(CNINFO_BACKFILL_ID_MIN) \
		--id-max $(CNINFO_BACKFILL_ID_MAX) \
		--shard-count $(CNINFO_BACKFILL_SHARD_COUNT) \
		--shard-index $(CNINFO_BACKFILL_SHARD_INDEX) \
		--workers $(CNINFO_BACKFILL_WORKERS) \
		--retries $(CNINFO_BACKFILL_RETRIES) \
		--sleep-sec $(CNINFO_BACKFILL_SLEEP) \
		--progress-every $(CNINFO_BACKFILL_PROGRESS_EVERY) \
		--heartbeat-sec $(CNINFO_BACKFILL_HEARTBEAT_SEC) \
		--detail-timeout-sec $(CNINFO_BACKFILL_DETAIL_TIMEOUT_SEC) \
		--pdf-timeout-sec $(CNINFO_BACKFILL_PDF_TIMEOUT_SEC) \
		--db-flush-every $(CNINFO_BACKFILL_DB_FLUSH_EVERY) \
		--fulltext-max-chars $(CNINFO_BACKFILL_MAX_CHARS)

events-run:
	$(PY) src/cli/events.py run --limit $(LIMIT) --skip-validate --db $(DB)

classify-pending:
	$(PY) src/cli/events.py classify-pending \
		--db $(DB) \
		--batch-size $(CLASSIFY_BATCH_SIZE) \
		--max-batches $(CLASSIFY_MAX_BATCHES)

reclassify-source:
	$(PY) src/cli/events.py reclassify-source \
		--db $(DB) \
		--source '$(RECLASSIFY_SOURCE)' \
		--batch-size $(RECLASSIFY_BATCH_SIZE) \
		--max-batches $(RECLASSIFY_MAX_BATCHES)

linking-run:
	$(PY) src/cli/linking.py run --db $(DB) --top-k $(TOP_K) --min-score $(MIN_SCORE)

link-events:
	$(PY) src/cli/linking.py link-events \
		--db $(DB) \
		--top-k $(TOP_K) \
		--min-score $(MIN_SCORE) \
		--progress-every $(LINK_PROGRESS_EVERY)

load-relations:
	$(PY) src/cli/graph.py load-relations --db $(DB) --input output/seeds/company_relations_seed.csv

propagate:
	$(PY) src/cli/graph.py propagate --db $(DB) --min-source-score $(MIN_SCORE) --min-propagation-score 0.20

graph-run:
	$(PY) src/cli/graph.py run --db $(DB) --input output/seeds/company_relations_seed.csv --min-source-score $(MIN_SCORE) --min-propagation-score 0.20

cluster-stats:
	$(PY) src/modules/events/jobs/cluster_stats_job.py --db $(DB)

backfill-event-features:
	$(PY) src/modules/events/jobs/backfill_structured_features_job.py \
		--db $(DB) \
		--batch-size $(RECLASSIFY_BATCH_SIZE) \
		--max-batches $(RECLASSIFY_MAX_BATCHES) \
		$(if $(EVENT_START),--start-date $(EVENT_START),) \
		$(if $(EVENT_END),--end-date $(EVENT_END),) \
		$(if $(filter 1,$(EVENT_ONLY_NEEDY)),--only-needy,) \
		$(if $(filter 1,$(EVENT_LLM)),--use-llm,) \
		$(if $(filter 1,$(EVENT_LOCAL_LLM_ONLY)),--local-llm-only,) \
		--llm-max-rows $(EVENT_LLM_MAX_ROWS) \
		--llm-confidence-threshold $(EVENT_LLM_CONFIDENCE_THRESHOLD) \
		--llm-progress-every $(EVENT_LLM_PROGRESS_EVERY)

refresh-event-features:
	$(PY) src/cli/events.py reclassify-source \
		--db $(DB) \
		--source '$(RECLASSIFY_SOURCE)' \
		--batch-size $(RECLASSIFY_BATCH_SIZE) \
		--max-batches $(RECLASSIFY_MAX_BATCHES)
	$(MAKE) backfill-event-features \
		DB=$(DB) \
		RECLASSIFY_BATCH_SIZE=$(RECLASSIFY_BATCH_SIZE) \
		RECLASSIFY_MAX_BATCHES=$(RECLASSIFY_MAX_BATCHES) \
		EVENT_START=$(EVENT_START) \
		EVENT_END=$(EVENT_END) \
		EVENT_ONLY_NEEDY=$(EVENT_ONLY_NEEDY) \
		EVENT_LLM=$(EVENT_LLM) \
		EVENT_LOCAL_LLM_ONLY=$(EVENT_LOCAL_LLM_ONLY) \
		EVENT_LLM_MAX_ROWS=$(EVENT_LLM_MAX_ROWS) \
		EVENT_LLM_CONFIDENCE_THRESHOLD=$(EVENT_LLM_CONFIDENCE_THRESHOLD) \
		EVENT_LLM_PROGRESS_EVERY=$(EVENT_LLM_PROGRESS_EVERY)
	$(PY) src/modules/events/jobs/cluster_stats_job.py --db $(DB)

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

db-summary:
	psql -d $(DB) -c "select 'companies' as table_name, count(*) as rows from companies union all select 'raw_documents', count(*) from raw_documents union all select 'structured_events', count(*) from structured_events union all select 'event_company_links', count(*) from event_company_links order by table_name;"
	psql -d $(DB) -c "select count(*) as events, count(*) filter (where event_subject_subtype='未细分') as unrefined_subtype, count(*) filter (where subject_entities='[]'::jsonb) as empty_entities from structured_events;"
	psql -d $(DB) -c "select count(*) as links, count(distinct structured_event_id) as linked_events, count(distinct company_id) as linked_companies, count(*) filter (where link_type='direct_match') as direct_links, count(*) filter (where link_type='industry_match') as industry_links, round(avg(final_link_score)::numeric, 4) as avg_score from event_company_links;"

db-storage-audit:
	psql -d $(DB) -f sql/inspect_storage_footprint.sql

db-raw-source-audit:
	$(PY) src/cli/quality.py sources --db $(DB) --start-date $(RAW_AUDIT_START) --end-date $(RAW_AUDIT_END) --top-n $(RAW_AUDIT_TOP_N)

db-raw-audit:
	$(PY) src/cli/quality.py raw --db $(DB) --start-date $(RAW_REFRESH_START) --end-date $(RAW_REFRESH_END) --top-n $(RAW_AUDIT_TOP_N)

db-normalize-raw-categories:
	$(PY) src/cli/quality.py normalize-raw-categories --db $(DB)

db-stage-clean:
	@test "$(YES)" = "1" || (echo "Refusing to truncate stage tables. Re-run with YES=1."; exit 1)
	psql -d $(DB) -c "TRUNCATE TABLE stg_event_candidates RESTART IDENTITY CASCADE;"
	psql -d $(DB) -c "TRUNCATE TABLE stg_structured_events RESTART IDENTITY CASCADE;"

ingest-full-raw:
	$(PY) src/cli/collect.py full-raw \
	  --db $(DB) \
	  --start-date $(RAW_REFRESH_START) \
	  --end-date $(RAW_REFRESH_END) \
	  --max-jobs $(RAW_REFRESH_MAX_JOBS) \
	  --min-content-length $(RAW_REFRESH_MIN_CONTENT_LENGTH) \
	  --target-body-rows $(RAW_REFRESH_TARGET_BODY_ROWS) \
	  --cninfo-max-symbols $(RAW_REFRESH_CNINFO_MAX_SYMBOLS) \
	  --cninfo-limit-per-symbol $(RAW_REFRESH_CNINFO_LIMIT_PER_SYMBOL) \
	  --cninfo-workers $(RAW_REFRESH_CNINFO_WORKERS) \
	  --cninfo-backfill-max-rows $(RAW_REFRESH_CNINFO_BACKFILL_ROWS) \
	  --cninfo-backfill-workers $(RAW_REFRESH_CNINFO_BACKFILL_WORKERS) \
	  --top-n $(RAW_AUDIT_TOP_N) \
	  $(if $(filter 1,$(RAW_REFRESH_FORCE)),--force,)

research-base-pipeline: collect-history classify-pending link-events db-summary

research-feature:
	$(PY) src/cli/research.py feature --db $(DB) --analysis-mode event-study --benchmark hs300 --event-windows 1,3,5 --time-budget-sec $(TIME_BUDGET) --max-rows $(MAX_ROWS) --api-timeout-sec $(API_TIMEOUT) --progress-every $(PROGRESS_EVERY) $(FEATURE_TOKEN_ARG)

research-train-samples:
	$(PY) src/cli/research.py train \
		--db $(DB) \
		--min-link-score $(MIN_SCORE) \
		--label-dataset output/event_return_dataset.csv

research-negative-samples:
	$(PY) src/cli/research.py controls --db $(DB) --max-per-day $(NEG_MAX_PER_DAY)

stats-import:
	$(PY) src/cli/linking.py import-company-stats --db $(DB) --source $(STATS_SOURCE) --days $(DAYS) --max-symbols $(STATS_MAX_SYMBOLS) --max-rows $(STATS_MAX_ROWS) --tushare-token-file $(TOKEN_FILE)

stats-load:
	$(PY) src/cli/linking.py load-company-stats --db $(DB)

profiles-import:
	$(PY) src/cli/linking.py import-company-profiles --db $(DB)

profiles-load:
	$(PY) src/cli/linking.py load-company-profiles --db $(DB)

market-env:
	$(PY) src/cli/linking.py load-market-environment --db $(DB)

sentiment-load:
	$(PY) src/cli/linking.py load-sentiment-propagation --db $(DB)

quality-check:
	$(PY) src/cli/quality.py check

quality-sample:
	$(PY) src/cli/quality.py sample --sample-size 50

quality-summary:
	$(PY) src/cli/quality.py summary --db $(DB)

delivery-status:
	$(PY) src/cli/quality.py delivery-status --db $(DB)

full: events-run link-events sentiment-load research-feature research-train-samples db-summary

full-with-market: full stats-import stats-load profiles-load market-env research-negative-samples db-summary

llm:
	$(PY) src/cli/events.py classify --db $(DB) --use-llm --llm-max-rows 10 --skip-db-load

trial: full stats-import stats-load profiles-load market-env quality-summary

go: full
