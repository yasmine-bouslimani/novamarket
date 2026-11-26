---
pretty_name: NovaMarket S5 - Agrégats de mobilité par zone TLC
tags:
  - education
  - novamarket
  - pyspark
license: cc-by-4.0
---

# NovaMarket S5 — Indicateurs agrégés par zone de départ (Données dérivées)

## Origine et conditions d'usage
- **Source analysée en streaming :** `DinoPonjevic/NYC_TaxiData` (révision `5941adbf8c0b9930e47002dc3103de3f9291360d`, partition `2024/yellow/yellow_tripdata_2024-01.parquet`) et référentiel officiel NYC TLC `zones.csv`.
- **Conformité :** Aucune ligne brute du miroir (licence `unknown`) n'est republiée. Ce dépôt contient uniquement des agrégats statistiques anonymisés calculés via PySpark.

## Colonnes et unités
Grain : **1 ligne = 1 zone de départ (`zone_id`)**.
- `zone_id` (`int32`) : identifiant officiel de la zone TLC.
- `arrondissement` (`string`) : borough NYC associé (ou `"Inconnu"` si non apparié).
- `nom_zone` (`string`) : libellé de la zone.
- `nb_trajets` (`int64`) : nombre de trajets valides observés dans l'échantillon.
- `distance_moy_km` (`double`) : distance moyenne convertie en **kilomètres** (1 mile = 1,60934 km).
- `duree_moy_min` (`double`) : durée moyenne en **minutes**.
- `vitesse_moy_kmh` (`double`) : vitesse moyenne en **km/h**.

## Extraction, qualité et limites
- **Streaming borné :** 500 premières lignes parcourues avant filtrage ; rejet des valeurs nulles, distances `<= 0` ou `> 500` miles, et durées `<= 0` ou `> 86400` s.
- **Limites :** Échantillon borné sur les premiers enregistrements de janvier 2024 (non représentatif de l'ensemble de l'année).

## Révisions
- **v1 :** Publication initiale des agrégats calculés sur l'échantillon de 500 trajets (`parquet_zones_v1`).
- **v2 :** Mise à jour des agrégats sur un échantillon élargi à 1 000 trajets (`parquet_zones_v2`) et enrichissement de la documentation des unités.