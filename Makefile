PY := python3
DB ?= stock_event_mining
LIMIT ?= 20
TOP_K ?= 3
MIN_SCORE ?= 0.35
TIME_BUDGET ?= 180
MAX_ROWS ?= 80
API_TIMEOUT ?= 10
PROGRESS_EVERY ?= 5
TOKEN_FILE ?= .secrets/tushare_token.txt
STATS_SOURCE ?= auto
DAYS ?= 30
NEG_MAX_PER_DAY ?= 100

.PHONY: help \
	collect link feature train status stats-import stats-load negatives \
	full full-with-stats \
	go r q c l f t s si sl n

help:
	@echo "最常用："
	@echo "  make go              # 跑一轮核心数据链（collect+link+feature+train+status）"
	@echo "  make r               # 完整训练底座（go + stats-import + stats-load + negatives + status）"
	@echo "  make q               # 快速采集（collect + status）"
	@echo ""
	@echo "完整命令："
	@echo "  make collect | link | feature | train | status"
	@echo "  make stats-import | stats-load | negatives"
	@echo ""
	@echo "短别名：c l f t s si sl n"

collect:
	$(PY) src/cli/task1.py run --limit $(LIMIT) --skip-validate --db $(DB)

link:
	$(PY) src/cli/task2.py run --db $(DB) --top-k $(TOP_K) --min-score $(MIN_SCORE)

feature:
	$(PY) src/cli/task1.py feature \
		--db $(DB) \
		--analysis-mode event-study \
		--benchmark hs300 \
		--event-windows 1,3,5 \
		--time-budget-sec $(TIME_BUDGET) \
		--max-rows $(MAX_ROWS) \
		--api-timeout-sec $(API_TIMEOUT) \
		--progress-every $(PROGRESS_EVERY) \
		--tushare-token-file $(TOKEN_FILE)

train:
	$(PY) src/cli/task1.py train-samples \
		--db $(DB) \
		--min-link-score $(MIN_SCORE) \
		--label-dataset output/task1_event_return_dataset.csv

status:
	$(PY) src/cli/task1.py db-status --db $(DB)

stats-import:
	$(PY) src/cli/task2.py import-company-stats --db $(DB) --source $(STATS_SOURCE) --days $(DAYS) --tushare-token-file $(TOKEN_FILE)

stats-load:
	$(PY) src/cli/task2.py load-company-stats --db $(DB)

negatives:
	$(PY) src/cli/task2.py build-negative-samples --db $(DB) --max-per-day $(NEG_MAX_PER_DAY)

full: collect link feature train status

full-with-stats: full stats-import stats-load negatives status

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
