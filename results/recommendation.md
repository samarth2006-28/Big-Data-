# Sizing recommendation (auto-generated)

- Baseline cluster: **1 cores**
- Fastest configuration: **8 cores**
- Cheapest configuration: **1 cores**
- Lowest-carbon configuration: **8 cores**
- **Recommended size: 4 cores** - the largest cluster with strong-scaling efficiency >= 0.6 and >= 15% runtime reduction over the previous size.

Beyond this point each added core buys little time while cost and carbon keep rising (see marginal_analysis.csv). **Edit the thresholds in your report to match your own business constraint (deadline, budget, carbon target).**

## Quality guard
AUC range across cluster sizes: 0.7589 - 0.7589 (spread 0.0000). If the spread is tiny, speed was not bought at the cost of accuracy.

## Energy measurement method
Runs by method: codecarbon=30
(`codecarbon` = measured/modelled by CodeCarbon; `tdp_fallback` = CPU-utilisation x TDP estimate.)
