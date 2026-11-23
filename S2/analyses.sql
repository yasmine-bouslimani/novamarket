-- ============================================================================
-- 1. CLASSEMENT DES PRODUITS PAR CATÉGORIE (RANK + CTE)
-- ============================================================================
WITH ventes_produits AS (
    -- Grain : 1 ligne = 1 produit (sur commandes 'completed' uniquement)
    SELECT 
        c.category_id,
        c.category_name,
        p.product_id,
        p.product_name,
        SUM(oi.quantity * oi.unit_price_cents) AS ca_cents
    FROM order_items oi
    JOIN orders o ON o.order_id = oi.order_id
    JOIN products p ON p.product_id = oi.product_id
    JOIN categories c ON c.category_id = p.category_id
    WHERE o.status = 'completed'
    GROUP BY c.category_id, c.category_name, p.product_id, p.product_name
)
SELECT 
    category_name,
    product_name,
    ca_cents,
    RANK() OVER (PARTITION BY category_id ORDER BY ca_cents DESC) AS rang_categorie
FROM ventes_produits
ORDER BY category_id, rang_categorie;

-- ============================================================================
-- 2. ÉVOLUTION MENSUELLE DES VENTES (LAG / LEAD)
-- ============================================================================
WITH ventes_mensuelles AS (
    SELECT 
        date_trunc('month', o.ordered_on)::date AS mois,
        COUNT(DISTINCT o.order_id) AS nb_commandes,
        SUM(oi.quantity * oi.unit_price_cents) AS ca_cents,
        MIN(o.ordered_on) AS premiere_date,
        MAX(o.ordered_on) AS derniere_date
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'completed'
    GROUP BY date_trunc('month', o.ordered_on)::date
)
SELECT 
    mois,
    nb_commandes,
    ca_cents,
    LAG(ca_cents) OVER (ORDER BY mois) AS ca_mois_precedent,
    ca_cents - LAG(ca_cents) OVER (ORDER BY mois) AS evolution_cents,
    LEAD(ca_cents) OVER (ORDER BY mois) AS ca_mois_suivant,
    premiere_date,
    derniere_date
FROM ventes_mensuelles
ORDER BY mois;

-- ============================================================================
-- 3. CONTRÔLE DE COHÉRENCE DES DATES (Ventes avant mise en vente)
-- ============================================================================
SELECT 
    o.order_id,
    o.ordered_on,
    p.product_id,
    p.product_name,
    p.first_listed_on,
    (oi.quantity * oi.unit_price_cents) AS montant_cents
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.ordered_on < p.first_listed_on
ORDER BY o.ordered_on;

-- ============================================================================
-- 4. SEGMENTATION DES CLIENTS EN 4 QUARTILES (NTILE(4) - Mission A1)
-- ============================================================================
WITH ca_clients AS (
    -- Population : les 180 clients (y compris les 30 clients à 0 €)
    SELECT 
        c.customer_id,
        c.customer_name,
        COALESCE(SUM(oi.quantity * oi.unit_price_cents), 0) AS ca_total_cents
    FROM customers c
    LEFT JOIN orders o ON o.customer_id = c.customer_id AND o.status = 'completed'
    LEFT JOIN order_items oi ON oi.order_id = o.order_id
    GROUP BY c.customer_id, c.customer_name
)
SELECT 
    customer_id,
    customer_name,
    ca_total_cents,
    -- Tri déterministe : CA décroissant, puis customer_id croissant en cas d'égalité
    NTILE(4) OVER (ORDER BY ca_total_cents DESC, customer_id ASC) AS quartile
FROM ca_clients
ORDER BY quartile, ca_total_cents DESC, customer_id;

-- ============================================================================
-- 5. HIÉRARCHIE DES CATÉGORIES ET CONSOLIDATION PAR BRANCHE (WITH RECURSIVE - A1)
-- ============================================================================
WITH RECURSIVE arbre_categories AS (
    -- Ancre : chaque catégorie est le point de départ de sa propre branche
    SELECT 
        category_id AS racine_id,
        category_name AS racine_nom,
        category_id AS enfant_id,
        0 AS profondeur,
        ARRAY[category_id] AS chemin
    FROM categories
    UNION ALL
    -- Récursion : descendre vers les sous-catégories en bloquant les cycles
    SELECT 
        ac.racine_id,
        ac.racine_nom,
        c.category_id AS enfant_id,
        ac.profondeur + 1,
        ac.chemin || c.category_id
    FROM arbre_categories ac
    JOIN categories c ON c.parent_category_id = ac.enfant_id
    WHERE NOT c.category_id = ANY(ac.chemin)
),
ca_direct_categorie AS (
    SELECT p.category_id, SUM(oi.quantity * oi.unit_price_cents) AS ca_cents
    FROM order_items oi
    JOIN orders o ON o.order_id = oi.order_id
    JOIN products p ON p.product_id = oi.product_id
    WHERE o.status = 'completed'
    GROUP BY p.category_id
)
SELECT 
    ac.racine_id AS category_id,
    ac.racine_nom AS category_name,
    COALESCE(SUM(cdc.ca_cents), 0) AS ca_consolide_branche_cents
FROM arbre_categories ac
LEFT JOIN ca_direct_categorie cdc ON cdc.category_id = ac.enfant_id
GROUP BY ac.racine_id, ac.racine_nom
ORDER BY ac.racine_id;