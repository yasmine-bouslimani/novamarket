from pyspark.sql import SparkSession

spark = (SparkSession.builder.master("local[2]").appName("diagnostic-s5")
         .config("spark.sql.shuffle.partitions","2").getOrCreate())
try:
    assert spark.range(5).count() == 5
    print("Spark local", spark.version, "opérationnel")
finally:
    spark.stop()
