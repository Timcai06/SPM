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

.PHONY: help full collect link feature train status stats-import stats-load negatives full-with-stats

help:
	@echo "make full              # task1 run + task2 link + feature + train + status"
	@echo "make collect           # task1 run --skip-validate"
	@echo "make link              # task2 event-company linking"
	@echo "make feature           # event-study labels"
	@echo "make train             # build model_event_samples"
	@echo "make status            # db-status"
	@echo "make stats-import      # import company_stats from tushare"
	@echo "make stats-load        # load company_stats into db"
	@echo "make negatives         # build model_non_event_samples"
	@echo "make full-with-stats   # full + company_stats + negatives"

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
