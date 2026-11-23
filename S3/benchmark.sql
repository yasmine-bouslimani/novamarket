-- Prérequis : avoir exécuté s3/generer.sql (10 000 000 lignes dans benchmark.benchmark_sales)

-- 1. VÉRIFICATION DU VOLUME ET DE LA TAILLE INITIALE
SELECT COUNT(*) AS nb_lignes FROM benchmark.benchmark_sales;
SELECT pg_size_pretty(pg_total_relation_size('benchmark.benchmark_sales')) AS taille_table;

-- 2. MESURES AVANT INDEX (Répéter 3 fois chacune pour relever la médiane)
-- Filtre A : Haute sélectivité (store_id = 42 -> 100 lignes sur 10 000 000, soit 0,001%)
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*), SUM(amount_cents)
FROM benchmark.benchmark_sales
WHERE store_id = 42;

-- Filtre B : Faible sélectivité (store_id = 1 -> 9 500 000 lignes sur 10 000 000, soit 95%)
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*), SUM(amount_cents)
FROM benchmark.benchmark_sales
WHERE store_id = 1;

-- 3. CRÉATION DE L'INDEX ET MESURE DE SON COÛT / TAILLE
\timing on
CREATE INDEX benchmark_sales_store_id_idx ON benchmark.benchmark_sales (store_id);
\timing off

ANALYZE benchmark.benchmark_sales;
SELECT pg_size_pretty(pg_relation_size('benchmark.benchmark_sales_store_id_idx')) AS taille_index;

-- 4. MESURES APRÈS INDEX (Répéter 3 fois chacune)
-- Filtre A (Haute sélectivité : bascule sur Index Scan / Bitmap Index Scan)
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*), SUM(amount_cents)
FROM benchmark.benchmark_sales
WHERE store_id = 42;

-- Filtre B (Faible sélectivité : l'optimiseur ignore l'index et garde un Parallel Seq Scan)
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*), SUM(amount_cents)
FROM benchmark.benchmark_sales
WHERE store_id = 1;

-- 5. ILLUSTRATION DU RISQUE DE MULTIPLICATION PAR JOINTURE (M4)
-- Mauvaise pratique : joindre directement les ventes et campaign_assignments
-- Le magasin 42 appartient à 2 campagnes (101 et 102) -> ses ventes sont doublées !
EXPLAIN (ANALYZE, BUFFERS)
SELECT bs.store_id, COUNT(*) AS nb_lignes_multipliees, SUM(bs.amount_cents) AS montant_fausse
FROM benchmark.benchmark_sales bs
JOIN benchmark.campaign_assignments ca ON ca.store_id = bs.store_id
WHERE bs.store_id = 42
GROUP BY bs.store_id;