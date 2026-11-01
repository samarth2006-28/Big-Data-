# Model Card: Click-prediction baseline (Spark MLlib logistic regression)

## Model details
- **Type:** Logistic regression on hashed features (13 log-scaled numeric + 26 categorical, `2^14` buckets in the reported runs; the script default is `2^18`), Spark MLlib, L2 regularisation `1e-5`, 10 iterations.
- **Purpose in this project:** a *fixed, cheap, reproducible workload* to study how training time, cost, energy and carbon change with cluster size. It is **not** a tuned production CTR model.
- **Version / code:** `scripts/02_train.py` at the commit tagged in the report. Hyper-parameters are recorded per run in `results/runs.jsonl`.

## Intended use
- Benchmarking distributed training efficiency and its carbon footprint; teaching/coursework.
- **Out of scope:** real ad targeting or any decision about real people. Features are anonymised and the model was not validated for deployment.

## Data
See `docs/data_card.md`. Criteo Display Advertising Challenge (`dac-v1`), deterministic 1,000,612-row subset of 45.8M rows; 80/20 deterministic split (801,066 train / 199,546 test).

## Metrics (strong-scaling runs, 1M-row subset)
| Metric | Value | Notes |
|---|---|---|
| Test AUC (overall) | 0.7589 | median over 15 strong-scaling runs (identical at every cluster size) |
| Test log-loss | 0.486 | |
| AUC, I1 present | 0.7491 | data-quality slice |
| AUC, I1 missing | 0.7428 | data-quality slice (I1 missing in 45.3% of rows) |
| AUC spread across cluster sizes | 0.0000 | should be ~0 if scaling does not change the model |

Reference: on the full 45.8M rows (one 16-core run, `2^18` buckets, 20 iterations) the same model reached AUC 0.786 / log-loss 0.463.

## Environmental impact (from `results/recommendation.md`)
| Item | Value |
|---|---|
| Hardware | Intel Core Ultra 9 185H (16 cores: 6P + 8E + 2LPE, 22 threads), 32 GB RAM, local laptop (Windows 11), Spark `local[N]` |
| Measurement | CodeCarbon (offline mode, `country_iso_code=IND`), machine-level tracking; all 30 runs measured by CodeCarbon (no TDP fallback) |
| Energy per full run at recommended size (4 cores) | 0.00103 kWh |
| CO2e per full run at recommended size (4 cores) | 0.00073 kg |
| Total experiment campaign | 0.0226 kg CO2e (30 reported runs, includes repeats); about 0.063 kg CO2e including the full-data reference run, the discarded first sweep and the pilot runs (57 runs) |

## Ethical considerations and limitations
- **Accuracy is not fairness:** anonymised features prevent auditing by protected groups. The only slice checked is data-quality-based. Real deployment would need user-group audits and consent/privacy review.
- **Carbon numbers are estimates:** CodeCarbon models power from CPU/RAM and grid intensity; it can miss network, storage, cooling and embodied emissions, and in VMs may fall back to TDP-based estimates. Treat values as relative comparisons between cluster sizes more than absolute truth.
- **Click prediction has societal costs:** optimising engagement can encourage manipulative targeting. This project does not deploy any model.
- **Hash collisions** blend rare categories, which may hurt rare-group accuracy.

## Contact
Sai Likhith S (PES1UG24AM239) · Samarth S A (PES1UG24AM243) · Nikhil Tej (PES1UG24AM311)
