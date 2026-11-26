# Évaluation Collective n°1 — Projet NovaMarket (S1 à S3)

## 1. Architecture et Exécution du Projet
Le dépôt regroupe l'ensemble des scripts reproductibles de la chaîne de données NovaMarket :
- `s1/import.sql` & `s1/indicateur.sql` : Création du schéma transactionnel, contrôle des rejets et calcul des indicateurs commerciaux de base.
- `s2/catalogue.sql` : Intégration des catégories et des produits, contrôle de couverture et ajout des clés étrangères.
- `s2/analyses.sql` : Requêtes analytiques avancées (`RANK`, `LAG`/`LEAD`, `NTILE`, `WITH RECURSIVE`) et audit temporel.
- `s3/benchmark.sql` : Tests de performance (`EXPLAIN (ANALYZE, BUFFERS)`) et d'indexation sur la table isolée `benchmark.benchmark_sales` (10 millions de lignes générées par `s3/generer.sql`).

---

## 2. Synthèse S1 — Modélisation, Rejets et Indicateurs Socles
- **Grains & Schéma :** `customers` (180) → `orders` (400) → `order_items` (800 retenus) et `payments` (480). Montants stockés en `integer` (centimes) pour éviter les erreurs d'arrondi flottant ; statuts verrouillés par contraintes `CHECK` sensibles à la casse.
- **Journal des rejets S1 (`order_items.csv` — 802 lignes reçues) :**
  - `order_item_id = 7` : doublon strict fusionné via `SELECT DISTINCT`.
  - `order_item_id = 801` : référence orpheline vers la commande inexistante `order_id = 9999`, écartée par filtrage référentiel.
- **Indicateurs clés (périmètre : commandes `completed`) :**
  - Répartition des commandes : 320 `completed`, 40 `pending`, 40 `cancelled` (et 30 clients sans commande).
  - CA réalisé : **26 210,00 €** (2 621 000 centimes).
  - Panier moyen : **81,91 €** (dénominateur explicite : 320 commandes terminées).
  - Rapprochement paiements (`captured` sur commandes `completed`) : **26 210,00 €** (écart = 0).

---

## 3. Synthèse S2 — Catalogue et Analyses Avancées

### M1 : Intégration du catalogue et anomalies
- **`categories.csv` :** 10 catégories intégrées (2 racines sans parent : *Maison* et *Loisirs*, 8 sous-catégories valides).
- **`products.csv` :** 25 lignes reçues → **24 produits intégrés**. La fiche `product_id = 3` (`NM-003`, *Article 03*) était dupliquée à l'identique (lignes 4 et 26) et a été dédoublonnée via `DISTINCT`.
- **Couverture :** Les 24 `product_id` du catalogue couvrent 100 % des produits vendus dans `order_items` (0 orphelin).

### M2 : Résultats des fonctions analytiques et limites
- **Classement par catégorie (`RANK()`) :**
  - *Effet de duplication :* Sans le dédoublonnage de `product_id = 3` dans la catégorie *Rangement* (11), son CA passe artificiellement de `23 625` à `47 250` centimes, le faisant passer de la 4e à la 3e place devant l'*Article 01* (`32 500` centimes).
- **Évolution mensuelle (`LAG()` / `LEAD()`) :**
  - Septembre 2026 (120 cmd) : **971 750** centimes (`9 717,50 €`).
  - Octobre 2026 (124 cmd) : **1 026 125** centimes (`10 261,25 €`, soit `+54 375` centimes / `+5,6 %`).
  - Novembre 2026 (76 cmd) : **623 125** centimes (`6 231,25 €`, soit `-403 000` centimes).
  - *Limite méthodologique (période incomplète) :* Les commandes de novembre s'arrêtent au **19/11/2026**. La baisse apparente de novembre n'est pas une chute d'activité mais un biais de période incomplète (19 jours contre 31 en octobre).
- **Incohérence de dates (`ordered_on < first_listed_on`) :**
  - **5 commandes** (IDs `5`, `22`, `29`, `46`, `53`, entre le 01/09/2026 et le 11/09/2026) contiennent l'*Article 06* (`product_id = 6`), alors que sa date officielle de première mise en vente est le **15/09/2026** (soit `6 250` centimes vendus avant la date catalogue).

### A1 : Segmentation (`NTILE(4)`) et Hiérarchie (`WITH RECURSIVE`)
- **Segmentation clients :** Sur la population totale des **180 clients** (45 par quartile, triés par `ca_total_cents DESC, customer_id ASC` pour stabiliser les égalités) :
  - Q1 (Top 25 %) : de `23 625` à `36 375` centimes (CA cumulé : `1 308 750` centimes).
  - Q2 : de `16 750` à `23 625` centimes (`899 125` centimes).
  - Q3 : de `0` à `16 750` centimes (`413 125` centimes).
  - Q4 : `0` centime (les 30 clients sans commande + 15 clients avec commandes uniquement `pending`/`cancelled`).
- **Consolidation par branche (`WITH RECURSIVE`) :**
  - Branche *Maison* (`id=1`) : **824 375** centimes (dont *Atelier* `476 625` = *Rangement* `166 625` + *Outillage* `310 000`, et *Cuisine* `347 750`).
  - Branche *Loisirs* (`id=2`) : **1 796 625** centimes (dont *Extérieur* `1 182 000` = *Jardin* `505 375` + *Randonnée* `676 625`, et *Jeux de table* `614 625`).
  - *Vérification :* `824 375 + 1 796 625 = 2 621 000` centimes (aucun double comptage, protection anti-cycle par tableau `chemin`).

---

## 4. Synthèse S3 — Benchmark, Indexation et Analyse Critique

| Scénario de test (10 000 000 lignes) | Sélectivité | Plan sans index | Plan avec index (`store_id`) | Interprétation technique |
|---|---|---|---|---|
| **Filtre A :** `WHERE store_id = 42` | **Haute** (`100` lignes = `0,001 %`) | `Parallel Seq Scan` (lecture intégrale des blocs de la table) | `Index Scan` / `Bitmap Index Scan` (accès direct aux pages ciblées) | **Gain majeur :** L'index évite de parcourir les 10 millions de lignes et réduit drastiquement les accès disques/tampons (`BUFFERS`). |
| **Filtre B :** `WHERE store_id = 1` | **Très faible** (`9 500 000` lignes = `95 %`) | `Parallel Seq Scan` | `Parallel Seq Scan` (**Index ignoré**) | **Cas d'index inefficace :** Lire 95 % de la table via des allers-retours index → table coûte plus cher qu'une lecture séquentielle directe. PostgreSQL écarte volontairement l'index. |

### Risques majeurs de jointure et d'estimation (M4 & A1)
1. **Multiplication des lignes par jointure multi-grains :**
   - Dans `benchmark`, le magasin `store_id = 42` est rattaché à **2 campagnes** (`101` et `102`) dans `campaign_assignments`. Une jointure directe `benchmark_sales JOIN campaign_assignments` duplique chacune de ses 100 ventes (200 lignes en sortie) et **double artificiellement son chiffre d'affaires**. Il faut toujours agréger par `store_id` avant de joindre les campagnes.
2. **Écart entre cardinalités estimées (`rows`) et réelles (`actual rows`) :**
   - Lorsqu'une colonne présente une forte asymétrie (comme `store_id` où la valeur `1` occupe 95 % des lignes et 5 000 autres magasins se partagent 5 %), un planificateur sans statistiques à jour (`ANALYZE`) sous-estime massivement les lignes de `store_id = 1` ou surestime les magasins rares, ce qui peut provoquer un mauvais choix de jointure (*Nested Loop* au lieu de *Hash Join*).
---

## 5. Séance S3 — Ingestion Asynchrone Python (`aiohttp` / `asyncio`)

### Contrat HTTP de l'API Fournisseur (Mission M1)
- **Endpoint :** `GET http://127.0.0.1:18080/offers?page={1..6}&scenario={clean|atelier|panne}&run={id}`
- **Pagination :** Numérotée (`page`, `total_pages = 6`, condition d'arrêt : `next_page` nul). Chaque page livre 4 offres (24 offres au total).
- **Contrat de données :** `offer_id` (texte unique, clé métier), `supplier_id` (`F01`, `F02` ou `F03`), `product_id` (entier `1..24` présent dans le catalogue S2), `price_cents` (entier >= 0), `currency` (`"EUR"`), `available_units` (entier >= 0), `observed_on` (date ISO `AAAA-MM-JJ`).
- **Exemple de réponse conforme :**
  ```json
  {"offer_id": "O001", "supplier_id": "F01", "product_id": 1, "price_cents": 625, "currency": "EUR", "available_units": 2, "observed_on": "2026-11-24"}

---

## 6. Séance S4 — Chargement PostgreSQL et Transformations dbt

### 1. Chargement Transactionnel & Idempotent (`transformation/chargement_postgres.py`)
- **Schéma et table cible :** `fournisseurs.offres_observees`, isolée des tables transactionnelles (`public`)[cite: 22].
- **Grain et clé primaire :** `(offer_id, observed_on)` — permet de conserver l'historique journalier d'une même offre sans duplication[cite: 25].
- **Atomicité et rejeu :** Transaction unique (`with conn.transaction():`) avec gestion des conflits `ON CONFLICT (offer_id, observed_on) DO UPDATE ... WHERE IS DISTINCT FROM`[cite: 22, 23].
  - **1er passage (`offres.jsonl`) :** 20 lignes lues, **20 insérées**, 0 rejetée[cite: 22].
  - **2nd passage (rejeu du même lot) :** 20 lignes lues, **0 insérée**, **20 inchangées** (idempotence validée)[cite: 22].

### 2. Architecture des modèles dbt (`transformation/dbt/`)
- **Sources (`models/staging/sources.yml`) :** `fournisseurs.offres_observees` (S3) et `public.products`, `public.orders`, `public.order_items` (S1–S2)[cite: 22].
- **Couches et matérialisations :**
  - `staging` (`view`) : `stg_offres`, `stg_products`, `stg_ventes_produits` (harmonisation des noms, conversion centimes → euros, pré-agrégation des ventes `completed` pour éviter toute multiplication artificielle de lignes)[cite: 22, 25].
  - `intermediate` (`view`) : `int_offres_enrichies` (jointure offres fournisseurs × catalogue produits et calcul de la marge unitaire)[cite: 22, 25].
  - `marts` (`table`) : `mart_comparaison_offres` (grain : 1 ligne = 1 offre observée à une date donnée, 20 lignes au total, comparant prix d'achat fournisseur, prix catalogue, marge et ventes historiques)[cite: 22, 25].
- **Tests et contrôles :** Tests `unique` / `not_null` sur les sources et test SQL personnalisé `test_prix_et_volumes_coherents.sql` exécutés avec succès via `dbt build`[cite: 20, 22].

---

## 7. Séance S5 — Streaming Hugging Face, PySpark et Hub

### 1. Organisation du travail et environnement (Binôme)
- **Répartition des tâches :** Mon poste Windows d'entreprise étant restreint (impossibilité d'installer Java 21, `winutils.exe` et les dépendances Python/Spark), j'ai conçu et rédigé l'ensemble des scripts (`collecte_streaming.py`, `traitement_spark.py`) ainsi que la Dataset Card (`volumetrie/publication/README.md`),
  ""
  pour toutes les taches que je n'ai pas fait sur mon pc j'ai suivi CHLOE sur cette partie la 
"""
### 2. Fiche Source & Streaming borné (`volumetrie/streaming/collecte_streaming.py`)
- **Dépôt source :** `DinoPonjevic/NYC_TaxiData` (révision `5941adbf8c0b9930e47002dc3103de3f9291360d`, 371 fichiers Parquet, ~39,35 Go).
- **Partition et colonnes :** `2024/yellow/yellow_tripdata_2024-01.parquet` (`Start_Zone`, `Trip_Distance` en miles, `Trip_Duration` en secondes).
- **Justification du streaming :** Le volume global (39,35 Go) rend un chargement intégral en RAM inadapté ; la lecture progressive (`streaming=True`) permet de borner le parcours et d'appliquer les filtres qualité à la volée avant fermeture de l'itérateur dans un bloc `finally`.
- **Mesures d'extraction (v1) :** **[500]** lignes parcourues avant filtrage → **[XXX]** retenues, **[XXX]** rejetées (valeurs nulles ou distances/durées incohérentes).

### 3. Pipeline PySpark (`volumetrie/spark/traitement_spark.py`)
- **Traitements :** Typage explicite, conversion des distances en kilomètres (`1 mile = 1,60934 km`), calcul de la vitesse moyenne (`km/h`), détection des zones non appariées (`left_anti`) avant jointure avec `zones.csv` dédupliqué, et agrégation par zone de départ.
- **Contrôles de volume et Parquet :**
  - Effectifs avant jointure : **[XXX]** trajets valides (dont **[X]** sans correspondance dans `zones.csv`).
  - Effectifs après jointure (`LEFT JOIN`) : **[XXX]** trajets (aucune multiplication artificielle).
  - Export au format Parquet (`mode("errorifexists")`) relu et vérifié par assertion de comptage (`df_relu.count() == df_agrege.count()`).

### 4. Publication et versionnement sur Hugging Face Hub (`volumetrie/publication/README.md`)  "Si j'avais la possibilité de le faire sur mon PC "
- **Conformité :** Aucune donnée brute du miroir (licence `unknown`) n'a été republiée ; seuls les indicateurs agrégés par zone et la Dataset Card ont été publiés.
- **Dépôt privé :** `https://huggingface.co/datasets/[COMPTE_HF]/novamarket-s5-exercice`
- **Révisions vérifiées :**
  - **v1** (échantillon 500 lignes) — SHA : `[COLLER_SHA_V1]`
  - **v2** (échantillon élargi à 1 000 lignes) — SHA : `[COLLER_SHA_V2]`
  - Récupération des deux révisions contrôlée via `hf download ... --revision <SHA>`.

