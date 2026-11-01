# Spark Cluster and Results Notebook (Part 3 of 3)

**BDSRAE Level 3 project** · Team: Sai Likhith S (PES1UG24AM239) · Samarth S A (PES1UG24AM243) · Nikhil Tej (PES1UG24AM311)

Reproducibility and presentation for the project *Distributed Training and Its Carbon Footprint*. Core experiment and results (Part 1): https://github.com/samarth2006-28/Big-Data-

```
docker/Dockerfile        one image for Spark master, workers and driver
docker-compose.yml       real Spark standalone cluster on one host (scale workers = cores)
Makefile                 shortcuts for the whole pipeline
notebooks/results.ipynb  regenerates every table and plot from results/runs.jsonl
results/                 real results (30 runs, 1M-row Criteo subset) the notebook reads
```

## Results notebook
Needs Python 3.10+ only (no Spark):
```bash
pip install pandas matplotlib jupyter
jupyter notebook notebooks/results.ipynb
```
It shows strong/weak scaling, cost and carbon, the time-vs-carbon trade-off, slice AUC and the sizing recommendation (4 cores).

## Docker cluster
Copy the `scripts/` and `src/` folders from Parts 1 and 2 into this folder first, since the cluster runs them. Then:
```bash
docker compose up -d --build --scale worker=8     # master + 8 single-core workers, UI at http://localhost:8080
docker compose exec driver python scripts/03_run_experiments.py --master spark://spark-master:7077 --cores-list 1 2 4 8 --repeats 3
docker compose down
```
Each worker offers exactly 1 core, so `--scale worker=N` gives N cores. Check that the Spark UI shows the expected number of workers before trusting results.

## Makefile
Targets: `setup`, `smoke`, `experiments`, `analyze`, `notebook`, `cluster-up`, `cluster-experiments`, `cluster-down`, `clean`. Most targets call scripts from Parts 1 and 2, so put all three parts in one folder to use them.
