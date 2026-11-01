"""Shared helpers: Criteo schema, Spark session builder, energy meter."""
import time
from contextlib import contextmanager

INT_COLS = [f"I{i}" for i in range(1, 14)]   # 13 numeric features
CAT_COLS = [f"C{i}" for i in range(1, 27)]   # 26 hashed categorical features
LABEL = "label"
CRITEO_COLUMNS = [LABEL] + INT_COLS + CAT_COLS

# Assumed on-demand price per vCPU-hour in USD (general-purpose cloud instance,
# e.g. AWS m5 is roughly $0.048/vCPU-h). Override with --price-per-vcpu-hour.
DEFAULT_PRICE_PER_VCPU_HOUR = 0.048


def get_spark(master="local[*]", app="criteo", driver_mem="2g", executor_mem="2g",
              shuffle_partitions=8, cores=None):
    """SparkSession. `master` is local[N] (simulated cluster of N cores) or
    spark://host:7077 (real standalone cluster, see docker-compose.yml)."""
    from pyspark.sql import SparkSession
    b = SparkSession.builder
    if cores and master.startswith("spark://"):
        b = b.config("spark.cores.max", str(cores))   # cap cores on a standalone cluster
    import os
    if os.environ.get("SPARK_DRIVER_HOST"):      # Docker Compose: executors must reach the driver
        b = (b.config("spark.driver.host", os.environ["SPARK_DRIVER_HOST"])
              .config("spark.driver.bindAddress", "0.0.0.0"))
    spark = (b.master(master).appName(app)
             .config("spark.driver.memory", driver_mem)
             .config("spark.executor.memory", executor_mem)
             .config("spark.sql.shuffle.partitions", str(shuffle_partitions))
             .config("spark.ui.showConsoleProgress", "false")
             .config("spark.sql.adaptive.enabled", "true")
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    return spark


class EnergyMeter:
    """Wraps CodeCarbon's OfflineEmissionsTracker (no network needed).

    Falls back to a CPU-utilisation x TDP estimate if CodeCarbon cannot read power
    (common in VMs/containers without RAPL access). `method` in the result records
    which path was used so the report can be honest about it.
    """

    def __init__(self, country_iso_code="IND", tdp_watts_per_core=10.0, cores=1,
                 project_name="criteo-scaling"):
        self.country = country_iso_code
        self.tdp = tdp_watts_per_core
        self.cores = cores
        self.project = project_name
        self.result = {}

    @contextmanager
    def measure(self):
        import psutil
        tracker = None
        try:
            from codecarbon import OfflineEmissionsTracker
            tracker = OfflineEmissionsTracker(
                project_name=self.project, country_iso_code=self.country,
                save_to_file=False, log_level="error", measure_power_secs=1,
                tracking_mode="machine")
            tracker.start()
        except Exception as e:
            print(f"[energy] CodeCarbon unavailable ({e}); using TDP fallback")
            tracker = None
        psutil.cpu_percent(None)
        t0 = time.time()
        try:
            yield
        finally:
            dt = time.time() - t0
            util = psutil.cpu_percent(None) / 100.0
            self.result = {}
            if tracker is not None:
                try:
                    kg = tracker.stop()
                    kwh = float(tracker.final_emissions_data.energy_consumed)
                    if kwh > 0:
                        self.result = {"energy_kwh": kwh, "co2e_kg": float(kg or 0.0),
                                       "method": "codecarbon"}
                except Exception as e:
                    print(f"[energy] CodeCarbon stop failed ({e}); using fallback")
            if not self.result:
                kwh = self.cores * self.tdp * max(util, 0.05) * dt / 3600.0 / 1000.0
                # ~0.71 kg CO2e/kWh: approximate Indian grid average (order of magnitude)
                self.result = {"energy_kwh": kwh, "co2e_kg": kwh * 0.71,
                               "method": "tdp_fallback"}
