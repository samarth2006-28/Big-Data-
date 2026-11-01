"""Generate synthetic data in the exact Criteo TSV layout (label, 13 ints, 26 hex cats).

Use for development and CI only. NOT a substitute for the real Criteo data in the
final results: it exists so the whole pipeline can be tested end to end anywhere.
Usage: python scripts/00_generate_synthetic.py --rows 200000 --out data/raw/synth.tsv
"""
import argparse, os
import numpy as np

p = argparse.ArgumentParser()
p.add_argument("--rows", type=int, default=200_000)
p.add_argument("--out", default="data/raw/synth.tsv")
p.add_argument("--seed", type=int, default=7)
p.add_argument("--chunk", type=int, default=50_000)
a = p.parse_args()

rng = np.random.default_rng(a.seed)
os.makedirs(os.path.dirname(a.out), exist_ok=True)
vocab = [rng.integers(0, 2**32, size=int(rng.integers(50, 5000)), dtype=np.uint64) for _ in range(26)]
w_int = rng.normal(0, 0.3, 13)
w_cat = [rng.normal(0, 0.5, len(v)) for v in vocab]

done = 0
with open(a.out, "w") as f:
    while done < a.rows:
        n = min(a.chunk, a.rows - done)
        ints = np.round(rng.lognormal(1.0, 1.2, (n, 13))).astype(int)
        ints_miss = rng.random((n, 13)) < 0.15
        idx = [rng.zipf(1.6, n) % len(v) for v in vocab]
        logit = -2.2 + (np.log1p(ints) @ w_int) * 0.4 + sum(w_cat[j][idx[j]] for j in range(26)) * 0.2
        y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
        for i in range(n):
            row = [str(y[i])]
            row += ["" if ints_miss[i, j] else str(ints[i, j]) for j in range(13)]
            row += [format(int(vocab[j][idx[j][i]]), "08x")[:8] if rng.random() > 0.03 else "" for j in range(26)]
            f.write("\t".join(row) + "\n")
        done += n
print(f"wrote {a.rows} rows to {a.out}")
