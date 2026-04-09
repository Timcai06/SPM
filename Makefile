PY := python3
DB ?= stock_event_mining
LIMIT ?= 20
TOP_K ?= 3
MIN_SCORE ?= 0.35
TIME_BUDGET ?= 180
MAX_ROWS ?= 200
API_TIMEOUT ?= 10
PROGRESS_EVERY ?= 5
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

FEATURE_TOKEN_ARG :=
ifeq ($(USE_TUSHARE),1)
FEATURE_TOKEN_ARG := --tushare-token-file $(TOKEN_FILE)
else
FEATURE_TOKEN_ARG := --disable-tushare
endif

.PHONY: help \
	collect link feature train status qa stats-import stats-load negatives \
	full full-with-stats backfill \
	text market llm trial \
	go r q c l f t s qa si sl n bf

help:
	@echo "推荐入口："
	@echo "  ./atk go             # 与 make go 等价（建议以后优先用 atk）"
	@echo "  ./atk bf             # 历史补报模式（多轮采集 + 扩公司统计特征）"
	@echo ""
	@echo "最常用："
	@echo "  make go              # 跑一轮核心数据链（collect+link+feature+train+status）"
	@echo "  make text            # 只扩文本事件链（等价于 make go）"
	@echo "  make market          # 只扩市场/公司特征（默认用 Sina）"
	@echo "  make llm             # 用本地 Ollama 做小批量事件结构化试点"
	@echo "  make trial           # 文本+市场一键试跑（适合日常）"
	@echo "  make r               # 完整训练底座（go + stats-import + stats-load + negatives + status）"
	@echo "  make q               # 快速采集（collect + status）"
	@echo ""
	@echo "完整命令："
	@echo "  make collect | link | feature | train | status | qa | backfill"
	@echo "  make stats-import | stats-load | negatives | full | full-with-stats"
	@echo ""
	@echo "短别名：c l f t s qa si sl n bf"

collect:
	$(PY) src/cli/task1.py run --limit $(LIMIT) --skip-validate --db $(DB)

link:
	$(PY) src/cli/task2.py run --db $(DB) --top-k $(TOP_K) --min-score $(MIN_SCORE)

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

stats-import:
	$(PY) src/cli/task2.py import-company-stats --db $(DB) --source $(STATS_SOURCE) --days $(DAYS) --max-symbols $(STATS_MAX_SYMBOLS) --max-rows $(STATS_MAX_ROWS) --tushare-token-file $(TOKEN_FILE)

stats-load:
	$(PY) src/cli/task2.py load-company-stats --db $(DB)

negatives:
	$(PY) src/cli/task2.py build-negative-samples --db $(DB) --max-per-day $(NEG_MAX_PER_DAY)

full: collect link feature train status

full-with-stats: full stats-import stats-load negatives status

text: full

market: stats-import stats-load qa

llm:
	$(PY) src/cli/task1.py classify --db $(DB) --use-llm --llm-max-rows 10 --skip-db-load

trial: full stats-import stats-load qa

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
si: stats-import
sl: stats-load
n: negatives
bf: backfill
