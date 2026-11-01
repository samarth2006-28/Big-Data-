"""Deterministic row subset of the prepared Parquet (same rows every time, keeps `rid`).

Use when the full data makes the scaling sweep too slow for your time budget, e.g.
  python scripts/01b_make_subset.py --data data/parquet/criteo --rows 1000000 --out data/parquet/criteo_1m
State the subset size in the report.
"""
import argparse, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pyspark.sql import functions as F
from src.common import get_spark

p = argparse.ArgumentParser()
p.add_argument("--data", default="data/parquet/criteo")
p.add_argument("--rows", type=int, default=1_000_000)
p.add_argument("--out", default="data/parquet/criteo_subset")
p.add_argument("--master", default="local[*]")
p.add_argument("--partitions", type=int, default=32)
a = p.parse_args()

spark = get_spark(a.master, "subset", driver_mem="8g")
df = spark.read.parquet(a.data)
total = df.count()
keep = int(round(a.rows / total * 1_000_000))            # buckets out of 1,000,000
df = df.filter(F.abs(F.hash("rid", F.lit(99))) % 1_000_000 < keep)
df.repartition(a.partitions).write.mode("overwrite").parquet(a.out)
n = spark.read.parquet(a.out).count()
print(f"Subset {n:,} of {total:,} rows -> {a.out}")
spark.stop()
