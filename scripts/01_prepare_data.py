"""Convert raw Criteo TSV (day_*.gz or train.txt) to partitioned Parquet.

Real data: download Criteo Display Advertising Challenge (small) or day_0..day_23 of the
1TB logs (see docs/data_card.md), then:
  python scripts/01_prepare_data.py --input "data/raw/day_0*.gz" --out data/parquet/criteo
Adds a stable `rid` column so every experiment samples exactly the same rows.
"""
import argparse, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pyspark.sql import functions as F, types as T
from src.common import get_spark, CRITEO_COLUMNS, INT_COLS, CAT_COLS

p = argparse.ArgumentParser()
p.add_argument("--input", required=True, help="path or glob of TSV / .gz files")
p.add_argument("--out", default="data/parquet/criteo")
p.add_argument("--master", default="local[*]")
p.add_argument("--partitions", type=int, default=32)
a = p.parse_args()

spark = get_spark(a.master, "prepare")
schema = T.StructType(
    [T.StructField("label", T.IntegerType())]
    + [T.StructField(c, T.IntegerType()) for c in INT_COLS]
    + [T.StructField(c, T.StringType()) for c in CAT_COLS])
df = (spark.read.option("sep", "\t").option("nullValue", "").schema(schema).csv(a.input)
      .withColumn("rid", F.monotonically_increasing_id()))
df.repartition(a.partitions).write.mode("overwrite").parquet(a.out)
n = spark.read.parquet(a.out).count()
print(f"Prepared {n:,} rows -> {a.out}")
spark.stop()
