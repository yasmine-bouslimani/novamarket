"""Mission M4 : Pipeline PySpark (typage, contrôle de jointure, agrégation, explain et Parquet relu)."""
import argparse
from pathlib import Path
from pyspark.sql import SparkSession, functions as F

RACINE_VOLUMETRIE = Path(__file__).resolve().parents[1]


def executer_pipeline_spark(entree_jsonl: Path, fichier_zones: Path, dossier_parquet: Path) -> None:
    if dossier_parquet.exists():
        raise FileExistsError(
            f"Le dossier de sortie existe déjà : {dossier_parquet}. Choisissez un chemin inédit."
        )

    spark = (
        SparkSession.builder.master("local[2]")
        .appName("NovaMarket-S5-Trajets")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )

    try:
        df_brut = spark.read.json(str(entree_jsonl))
        df_zones_brut = spark.read.option("header", True).csv(str(fichier_zones))

        print("=== SCHÉMA BRUT TRAJETS ===")
        df_brut.printSchema()
        print("Partitions initiales :", df_brut.rdd.getNumPartitions())

        col_zone_id = "LocationID" if "LocationID" in df_zones_brut.columns else df_zones_brut.columns[0]
        col_borough = "Borough" if "Borough" in df_zones_brut.columns else df_zones_brut.columns[1]
        col_zone_nom = "Zone" if "Zone" in df_zones_brut.columns else df_zones_brut.columns[-1]

        df_trajets = (
            df_brut.select(
                F.col("Start_Zone").cast("int").alias("zone_id"),
                F.col("Trip_Distance").cast("double").alias("distance_miles"),
                F.col("Trip_Duration").cast("double").alias("duree_sec"),
            )
            .where("zone_id IS NOT NULL AND distance_miles > 0 AND duree_sec > 0")
            .withColumn("distance_km", F.round(F.col("distance_miles") * 1.60934, 3))
            .withColumn("vitesse_kmh", F.round(F.col("distance_km") / (F.col("duree_sec") / 3600.0), 2))
        )

        df_zones = (
            df_zones_brut.select(
                F.col(col_zone_id).cast("int").alias("zone_id"),
                F.col(col_borough).alias("arrondissement"),
                F.col(col_zone_nom).alias("nom_zone"),
            )
            .where("zone_id IS NOT NULL")
            .dropDuplicates(["zone_id"])
        )

        nb_trajets_avant = df_trajets.count()
        nb_zones_ref = df_zones.count()
        non_apparies = df_trajets.join(df_zones, on="zone_id", how="left_anti")
        nb_non_apparies = non_apparies.count()

        print(f"Effectifs avant jointure : {nb_trajets_avant} trajets | {nb_zones_ref} zones de référence")
        print(f"Trajets sans correspondance dans zones.csv (left_anti) : {nb_non_apparies}")
        if nb_non_apparies > 0:
            non_apparies.show(10, truncate=False)

        df_enrichi = df_trajets.join(df_zones, on="zone_id", how="left").fillna(
            {"arrondissement": "Inconnu", "nom_zone": "Zone hors référentiel"}
        )
        nb_trajets_apres = df_enrichi.count()
        assert nb_trajets_apres == nb_trajets_avant, (
            f"Multiplication détectée : {nb_trajets_avant} -> {nb_trajets_apres}"
        )
        print(f"Effectifs après jointure : {nb_trajets_apres} trajets (aucune multiplication)")

        df_agrege = (
            df_enrichi.groupBy("zone_id", "arrondissement", "nom_zone")
            .agg(
                F.count("*").alias("nb_trajets"),
                F.round(F.avg("distance_km"), 2).alias("distance_moy_km"),
                F.round(F.avg("duree_sec") / 60.0, 2).alias("duree_moy_min"),
                F.round(F.avg("vitesse_kmh"), 2).alias("vitesse_moy_kmh"),
            )
            .orderBy(F.desc("nb_trajets"), F.asc("zone_id"))
        )

        print("=== PLAN D'EXÉCUTION PHYSIQUE (EXPLAIN) ===")
        df_agrege.explain()

        df_agrege.write.mode("errorifexists").parquet(str(dossier_parquet))

        df_relu = spark.read.parquet(str(dossier_parquet))
        print("=== CONTRÔLE DU PARQUET RELU ===")
        df_relu.printSchema()
        df_relu.show(20, truncate=False)
        assert df_relu.count() == df_agrege.count(), "Écart de comptage à la relecture Parquet !"
        print(f"Export Parquet validé ({df_relu.count()} lignes agrégées dans {dossier_parquet}).")

    finally:
        spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Traitement PySpark NovaMarket S5")
    parser.add_argument(
        "--entree",
        type=Path,
        default=RACINE_VOLUMETRIE / "sorties" / "trajets_valides.jsonl",
    )
    parser.add_argument(
        "--zones",
        type=Path,
        default=RACINE_VOLUMETRIE / "secours" / "zones.csv",
    )
    parser.add_argument(
        "--sortie",
        type=Path,
        default=RACINE_VOLUMETRIE / "sorties" / "parquet_zones_v1",
    )
    args = parser.parse_args()
    executer_pipeline_spark(args.entree, args.zones, args.sortie)