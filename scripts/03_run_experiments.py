"""Run strong- and weak-scaling experiments. Each run is a fresh process / JVM.

Strong scaling: fixed data (fraction=1.0), cores in --cores-list.
Weak scaling:   data fraction = cores / max(cores), so work-per-core stays constant.
  python scripts/03_run_experiments.py --cores-list 1 2 4 8 --repeats 3
Use --master spark://localhost:7077 to run on the Docker Compose cluster instead of local[N].
"""
import argparse, subprocess, sys, os
p = argparse.ArgumentParser()
p.add_argument("--data", default="data/parquet/criteo")
p.add_argument("--cores-list", type=int, nargs="+", default=[1, 2, 4, 8])
p.add_argument("--repeats", type=int, default=3)
p.add_argument("--skip-weak", action="store_true")
p.add_argument("--skip-strong", action="store_true")
p.add_argument("--master", default=None)
p.add_argument("--hash-bits", type=int, default=18)
p.add_argument("--max-iter", type=int, default=20)
p.add_argument("--driver-mem", default="2g")
p.add_argument("--executor-mem", default="2g")
p.add_argument("--out", default="results/runs.jsonl")
a = p.parse_args()

here = os.path.dirname(os.path.abspath(__file__))
mx = max(a.cores_list)
jobs = []
for rep in range(a.repeats):
    for c in a.cores_list:
        if not a.skip_strong:
            jobs.append(("strong", c, 1.0))
        if not a.skip_weak:
            jobs.append(("weak", c, round(c / mx, 4)))
for i, (mode, c, frac) in enumerate(jobs, 1):
    cmd = [sys.executable, os.path.join(here, "02_train.py"), "--data", a.data, "--cores", str(c),
           "--fraction", str(frac), "--mode", mode, "--hash-bits", str(a.hash_bits),
           "--max-iter", str(a.max_iter), "--driver-mem", a.driver_mem,
           "--executor-mem", a.executor_mem, "--out", a.out]
    if a.master:
        cmd += ["--master", a.master]
    print(f"[{i}/{len(jobs)}] {mode} cores={c} fraction={frac}", flush=True)
    subprocess.run(cmd, check=True)
print("All runs complete ->", a.out)
