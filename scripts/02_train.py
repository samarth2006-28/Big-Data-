"""Train a click-prediction model (hashed-feature logistic regression) with Spark
and record time, accuracy, cost, energy and carbon for ONE configuration.

Appends one JSON line to results/runs.jsonl. Run via 03_run_experiments.py so every
configuration runs in a fresh JVM, or call directly:
  python scripts/02_train.py --data data/parquet/criteo --cores 4 --fraction 1.0 --mode strong
"""
import argparse, json, os, sys, time, uuid, platform
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from pyspark.sql import functions as F
from pyspark.ml import Pipeline
from pyspark.ml.feature import FeatureHasher
from pyspark.ml.classification import LogisticRegression
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml.functions import vector_to_array
from src.common import (get_spark, EnergyMeter, INT_COLS, CAT_COLS,
                        DEFAULT_PRICE_PER_VCPU_HOUR)

p = argparse.ArgumentParser()
p.add_argument("--data", default="data/parquet/criteo")
p.add_argument("--cores", type=int, required=True, help="cores in the (simulated) cluster")
p.add_argument("--master", default=None, help="default local[cores]; or spark://host:7077")
p.add_argument("--fraction", type=float, default=1.0, help="share of rows to use (weak scaling)")
p.add_argument("--mode", default="strong", choices=["strong", "weak", "adhoc"])
p.add_argument("--hash-bits", type=int, default=18)
p.add_argument("--max-iter", type=int, default=20)
p.add_argument("--reg", type=float, default=1e-5)
p.add_argument("--driver-mem", default="2g")
p.add_argument("--executor-mem", default="2g")
p.add_argument("--price-per-vcpu-hour", type=float, default=DEFAULT_PRICE_PER_VCPU_HOUR)
p.add_argument("--country", default="IND", help="ISO code for grid carbon intensity")
p.add_argument("--tag", default="")
p.add_argument("--out", default="results/runs.jsonl")
a = p.parse_args()

master = a.master or f"local[{a.cores}]"
spark = get_spark(master, f"train-{a.cores}c", a.driver_mem, a.executor_mem,
                  shuffle_partitions=max(2, a.cores * 2), cores=a.cores)
meter = EnergyMeter(country_iso_code=a.country, cores=a.cores)
res = {"run_id": uuid.uuid4().hex[:8], "mode": a.mode, "cores": a.cores, "fraction": a.fraction,
       "master": master, "hash_bits": a.hash_bits, "max_iter": a.max_iter, "tag": a.tag,
       "host_cpus": os.cpu_count(), "platform": platform.platform(),
       "spark": spark.version, "price_per_vcpu_hour": a.price_per_vcpu_hour,
       "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}

with meter.measure():
    t0 = time.time()
    df = spark.read.parquet(a.data)
    bucket = F.abs(F.hash("rid")) % 10000
    if a.fraction < 1.0:   # deterministic subsample: same rows for same fraction
        df = df.filter(bucket < int(a.fraction * 10000))
    df = df.withColumn("I1_missing", F.col("I1").isNull().cast("int"))
    for c in INT_COLS:     # impute 0, then log1p to tame the heavy tails
        df = df.withColumn(c, F.log1p(F.greatest(F.coalesce(F.col(c), F.lit(0)), F.lit(0))).cast("double"))
    df = df.fillna("__missing__", subset=CAT_COLS)
    split = F.abs(F.hash("rid", F.lit(17))) % 10 < 2          # fixed 80/20 split
    df = df.repartition(a.cores * 2)
    train, test = df.filter(~split).cache(), df.filter(split).cache()
    res["rows_train"], res["rows_test"] = train.count(), test.count()
    res["load_s"] = time.time() - t0

    t1 = time.time()
    hasher = FeatureHasher(inputCols=INT_COLS + CAT_COLS, outputCol="features",
                           categoricalCols=CAT_COLS, numFeatures=2 ** a.hash_bits)
    lr = LogisticRegression(featuresCol="features", labelCol="label",
                            maxIter=a.max_iter, regParam=a.reg, aggregationDepth=2)
    model = Pipeline(stages=[hasher, lr]).fit(train)
    res["fit_s"] = time.time() - t1

    t2 = time.time()
    pred = model.transform(test).withColumn("p1", vector_to_array("probability")[1]).cache()
    ev = BinaryClassificationEvaluator(labelCol="label", rawPredictionCol="rawPrediction",
                                       metricName="areaUnderROC")
    res["auc"] = ev.evaluate(pred)
    eps = 1e-12
    ll = pred.select((-(F.col("label") * F.log(F.greatest(F.col("p1"), F.lit(eps)))
                        + (1 - F.col("label")) * F.log(F.greatest(1 - F.col("p1"), F.lit(eps))))
                      ).alias("ll")).agg(F.avg("ll")).first()[0]
    res["logloss"] = float(ll)
    # Responsible-AI slice check: does speed/quality trade-off hurt a data-quality slice?
    for name, cond in [("auc_i1_missing", pred.I1_missing == 1), ("auc_i1_present", pred.I1_missing == 0)]:
        sub = pred.filter(cond)
        try:
            res[name] = ev.evaluate(sub) if sub.select("label").distinct().count() == 2 else None
        except Exception:
            res[name] = None
    res["eval_s"] = time.time() - t2
    res["total_s"] = time.time() - t0

res.update(meter.result)
res["cost_usd"] = a.cores * (res["total_s"] / 3600.0) * a.price_per_vcpu_hour
res["gco2e_per_1k_rows"] = res["co2e_kg"] * 1000 * 1000 / max(res["rows_train"], 1)

os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
with open(a.out, "a") as f:
    f.write(json.dumps(res) + "\n")
print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in res.items()
                  if k in ("run_id", "mode", "cores", "fraction", "rows_train", "fit_s", "total_s",
                           "auc", "logloss", "energy_kwh", "co2e_kg", "cost_usd", "method")}))
spark.stop()
