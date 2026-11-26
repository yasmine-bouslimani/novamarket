"""Exemple indépendant : volumes mesurés par atelier."""
import argparse
from pathlib import Path

from pyspark.sql import SparkSession, functions as F

parser = argparse.ArgumentParser()
parser.add_argument("sortie", type=Path)
args = parser.parse_args()
spark = (SparkSession.builder.master("local[2]").appName("cuves")
         .config("spark.sql.shuffle.partitions", "2").getOrCreate())
try:
    mesures = spark.createDataFrame([(1, "12.5"), (1, "20"), (2, "-1"), (2, "3")], ["cuve", "brut"])
    cuves = spark.createDataFrame([(1, "A"), (2, "B")], ["cuve", "atelier"])
    mesures.printSchema()
    print("Partitions avant traitement :", mesures.rdd.getNumPartitions())
    resultat = (mesures.select("cuve", F.col("brut").cast("double").alias("litres"))
                .where("litres >= 0").join(cuves, "cuve")
                .withColumn("millilitres", F.col("litres") * 1000)
                .groupBy("atelier").sum("millilitres"))
    resultat.explain()
    resultat.write.mode("errorifexists").parquet(str(args.sortie))
    spark.read.parquet(str(args.sortie)).orderBy("atelier").show()
finally:
    spark.stop()
