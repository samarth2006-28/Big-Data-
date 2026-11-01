PY ?= python3
CORES ?= 1 2 4 8
REPEATS ?= 3
ROWS ?= 50000

.PHONY: setup synth prepare-synth smoke experiments analyze notebook cluster-up cluster-experiments cluster-down clean
setup:            ## install python deps (needs Java 11/17/21)
	$(PY) -m pip install -r requirements.txt
synth:            ## synthetic (ROWS=50000 default) file in Criteo layout (pipeline testing ONLY)
	$(PY) scripts/00_generate_synthetic.py --rows $(ROWS) --out data/raw/synth.tsv
prepare-synth: synth
	$(PY) scripts/01_prepare_data.py --input data/raw/synth.tsv --out data/parquet/criteo
smoke: prepare-synth  ## fast end-to-end check (minutes) - do NOT report these numbers
	$(PY) scripts/03_run_experiments.py --cores-list 1 2 --repeats 1 --hash-bits 14 --max-iter 8 --out results/smoke.jsonl
	$(PY) scripts/04_analyze.py --runs results/smoke.jsonl --outdir results/smoke
experiments:      ## real runs: assumes data/parquet/criteo exists (see README step 3)
	$(PY) scripts/03_run_experiments.py --cores-list $(CORES) --repeats $(REPEATS)
analyze:
	$(PY) scripts/04_analyze.py
notebook:
	jupyter notebook notebooks/results.ipynb
cluster-up:
	docker compose up -d --build --scale worker=$(shell echo $(CORES) | tr ' ' '\n' | sort -n | tail -1)
cluster-experiments:
	docker compose exec driver python scripts/03_run_experiments.py --master spark://spark-master:7077 --cores-list $(CORES) --repeats $(REPEATS)
cluster-down:
	docker compose down
clean:
	rm -rf spark-warehouse metastore_db derby.log results/smoke results/smoke.jsonl
