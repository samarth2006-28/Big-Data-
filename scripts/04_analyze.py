"""Aggregate results/runs.jsonl -> tables, scaling plots, energy report and sizing recommendation.

  python scripts/04_analyze.py --runs results/runs.jsonl --outdir results --efficiency-threshold 0.6
Outputs: summary_strong.csv, summary_weak.csv, marginal_analysis.csv, recommendation.md,
         strong_scaling.png, weak_scaling.png, cost_carbon.png, tradeoff.png, slice_auc.png
"""
import argparse, json, os
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

p = argparse.ArgumentParser()
p.add_argument("--runs", default="results/runs.jsonl")
p.add_argument("--outdir", default="results")
p.add_argument("--efficiency-threshold", type=float, default=0.6,
               help="min strong-scaling parallel efficiency to call a size 'worthwhile'")
p.add_argument("--min-marginal-gain", type=float, default=0.15,
               help="also require each doubling to cut runtime by at least this fraction")
a = p.parse_args()
os.makedirs(a.outdir, exist_ok=True)

rows = [json.loads(l) for l in open(a.runs) if l.strip()]
df = pd.DataFrame(rows)
metrics = ["fit_s", "total_s", "auc", "logloss", "energy_kwh", "co2e_kg", "cost_usd",
           "auc_i1_missing", "auc_i1_present", "rows_train"]
metrics = [m for m in metrics if m in df.columns]


def agg(mode):
    d = df[df["mode"] == mode]
    if d.empty:
        return pd.DataFrame()
    g = d.groupby("cores")
    out = g[metrics].median()
    out["n_runs"] = g.size()
    for m in ("fit_s", "total_s", "energy_kwh", "co2e_kg"):   # run-to-run spread
        out[m + "_std"] = g[m].std().fillna(0.0)
    return out.reset_index().sort_values("cores")

S, W = agg("strong"), agg("weak")
msg = []

# ---- strong scaling ----
if not S.empty:
    b = S.iloc[0]
    S["speedup_fit"] = b.fit_s / S.fit_s
    S["speedup_total"] = b.total_s / S.total_s
    S["efficiency"] = S.speedup_fit / (S.cores / b.cores)
    S["ideal"] = S.cores / b.cores
    S.to_csv(f"{a.outdir}/summary_strong.csv", index=False)

    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].plot(S.cores, S.speedup_fit, "o-", label="measured (fit)")
    ax[0].plot(S.cores, S.speedup_total, "s--", label="measured (end-to-end)")
    ax[0].plot(S.cores, S.ideal, "k:", label="ideal linear")
    ax[0].set_xlabel("cores"); ax[0].set_ylabel("speedup vs smallest cluster")
    ax[0].set_title("Strong scaling: speedup"); ax[0].legend(); ax[0].grid(alpha=.3)
    ax[1].plot(S.cores, S.efficiency, "o-", color="tab:red")
    ax[1].axhline(a.efficiency_threshold, ls="--", color="gray", label=f"threshold {a.efficiency_threshold}")
    ax[1].set_xlabel("cores"); ax[1].set_ylabel("parallel efficiency"); ax[1].set_ylim(0, 1.15)
    ax[1].set_title("Strong scaling: efficiency"); ax[1].legend(); ax[1].grid(alpha=.3)
    plt.tight_layout(); plt.savefig(f"{a.outdir}/strong_scaling.png", dpi=150); plt.close()

    # cost / energy / carbon vs cores
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
    for axi, col, lab in zip(ax, ["cost_usd", "energy_kwh", "co2e_kg"],
                             ["cost (USD)", "energy (kWh)", "carbon (kg CO2e)"]):
        e = S[col + "_std"] if col + "_std" in S else None
        axi.errorbar(S.cores, S[col], yerr=e, fmt="o-", capsize=3)
        axi.set_xlabel("cores"); axi.set_ylabel(lab); axi.set_title(lab + " per full training run")
        axi.grid(alpha=.3)
    plt.tight_layout(); plt.savefig(f"{a.outdir}/cost_carbon.png", dpi=150); plt.close()

    # time vs carbon trade-off
    fig, axx = plt.subplots(figsize=(5.5, 4.2))
    axx.plot(S.co2e_kg * 1000, S.total_s, "o-")
    for _, r in S.iterrows():
        axx.annotate(f"{int(r.cores)}c", (r.co2e_kg * 1000, r.total_s), textcoords="offset points", xytext=(5, 5))
    axx.set_xlabel("carbon (g CO2e)"); axx.set_ylabel("end-to-end time (s)")
    axx.set_title("Time vs carbon trade-off"); axx.grid(alpha=.3)
    plt.tight_layout(); plt.savefig(f"{a.outdir}/tradeoff.png", dpi=150); plt.close()

    # marginal analysis
    m = []
    for i in range(1, len(S)):
        x0, x1 = S.iloc[i - 1], S.iloc[i]
        saved = x0.total_s - x1.total_s
        dco2 = (x1.co2e_kg - x0.co2e_kg) * 1000
        m.append({"from_cores": int(x0.cores), "to_cores": int(x1.cores),
                  "time_saved_s": saved, "time_saved_pct": saved / x0.total_s * 100,
                  "extra_gCO2e": dco2, "extra_usd": x1.cost_usd - x0.cost_usd,
                  "sec_saved_per_extra_gCO2e": saved / dco2 if dco2 > 0 else np.inf})
    M = pd.DataFrame(m); M.to_csv(f"{a.outdir}/marginal_analysis.csv", index=False)

    # recommendation: largest size that still meets efficiency AND marginal-gain thresholds
    ok = []
    for i, r in S.reset_index(drop=True).iterrows():
        gain_ok = True if i == 0 else (S.iloc[i - 1].total_s - r.total_s) / S.iloc[i - 1].total_s >= a.min_marginal_gain
        ok.append(bool(r.efficiency >= a.efficiency_threshold and gain_ok))
    S["worthwhile"] = ok
    rec = int(S[S.worthwhile].cores.max()) if any(ok) else int(S.cores.min())
    cheapest = int(S.loc[S.cost_usd.idxmin(), "cores"])
    greenest = int(S.loc[S.co2e_kg.idxmin(), "cores"])
    fastest = int(S.loc[S.total_s.idxmin(), "cores"])
    msg += [f"# Sizing recommendation (auto-generated)\n",
            f"- Baseline cluster: **{int(S.iloc[0].cores)} cores**",
            f"- Fastest configuration: **{fastest} cores**",
            f"- Cheapest configuration: **{cheapest} cores**",
            f"- Lowest-carbon configuration: **{greenest} cores**",
            f"- **Recommended size: {rec} cores** - the largest cluster with strong-scaling efficiency "
            f">= {a.efficiency_threshold} and >= {int(a.min_marginal_gain*100)}% runtime reduction over the previous size.",
            "", "Beyond this point each added core buys little time while cost and carbon keep rising "
            "(see marginal_analysis.csv). **Edit the thresholds in your report to match your own "
            "business constraint (deadline, budget, carbon target).**", ""]
    if (S.method if "method" in S else None) is not None:
        pass

# ---- weak scaling ----
if not W.empty:
    b = W.iloc[0]
    W["efficiency"] = b.fit_s / W.fit_s          # ideal = 1.0 (flat runtime)
    W["rows_per_core"] = W.rows_train / W.cores
    W.to_csv(f"{a.outdir}/summary_weak.csv", index=False)
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].plot(W.cores, W.fit_s, "o-", label="measured fit time")
    ax[0].axhline(b.fit_s, ls=":", color="k", label="ideal (flat)")
    ax[0].set_xlabel("cores (data grows proportionally)"); ax[0].set_ylabel("fit time (s)")
    ax[0].set_title("Weak scaling: runtime"); ax[0].legend(); ax[0].grid(alpha=.3)
    ax[1].plot(W.cores, W.efficiency, "o-", color="tab:green")
    ax[1].axhline(1.0, ls=":", color="k"); ax[1].set_ylim(0, 1.3)
    ax[1].set_xlabel("cores"); ax[1].set_ylabel("weak-scaling efficiency")
    ax[1].set_title("Weak scaling: efficiency"); ax[1].grid(alpha=.3)
    plt.tight_layout(); plt.savefig(f"{a.outdir}/weak_scaling.png", dpi=150); plt.close()

# ---- responsible-AI slice check: does scale change quality on the I1-missing slice? ----
if not S.empty and "auc_i1_missing" in S and S.auc_i1_missing.notna().any():
    fig, axx = plt.subplots(figsize=(6, 3.8))
    axx.plot(S.cores, S.auc, "o-", label="overall AUC")
    axx.plot(S.cores, S.auc_i1_present, "s--", label="I1 present")
    axx.plot(S.cores, S.auc_i1_missing, "^--", label="I1 missing")
    axx.set_xlabel("cores"); axx.set_ylabel("test AUC"); axx.legend(); axx.grid(alpha=.3)
    axx.set_title("Model quality across cluster sizes and data slices")
    plt.tight_layout(); plt.savefig(f"{a.outdir}/slice_auc.png", dpi=150); plt.close()
    msg += ["## Quality guard", f"AUC range across cluster sizes: {S.auc.min():.4f} - {S.auc.max():.4f} "
            f"(spread {S.auc.max()-S.auc.min():.4f}). If the spread is tiny, speed was not bought at the cost of accuracy.", ""]

if "method" in df:
    msg += ["## Energy measurement method", "Runs by method: " + ", ".join(f"{k}={v}" for k, v in df.method.value_counts().items()),
            "(`codecarbon` = measured/modelled by CodeCarbon; `tdp_fallback` = CPU-utilisation x TDP estimate.)", ""]
open(f"{a.outdir}/recommendation.md", "w").write("\n".join(msg))
print("\n".join(msg))
if not S.empty:
    print(S[["cores", "fit_s", "total_s", "speedup_fit", "efficiency", "cost_usd", "energy_kwh", "co2e_kg", "auc"]].round(4).to_string(index=False))
