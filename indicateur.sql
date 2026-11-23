-- 1. Commandes par statut
SELECT status, COUNT(*) AS nb_commandes 
FROM orders 
GROUP BY status;

-- 2. Clients sans commande
SELECT COUNT(c.customer_id) AS nb_sans_commande 
FROM customers c 
LEFT JOIN orders o ON c.customer_id = o.customer_id 
WHERE o.order_id IS NULL;

-- 3. CA et Panier moyen (Commandes terminées uniquement)
WITH stats_cmd AS (
    SELECT o.order_id, SUM(oi.quantity * oi.unit_price_cents) AS total_cmd
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.status = 'completed'
    GROUP BY o.order_id
)
SELECT 
    SUM(total_cmd) AS CA_total_centimes,
    COUNT(order_id) AS denominateur_commandes,
    AVG(total_cmd) AS panier_moyen_centimes
FROM stats_cmd;

-- 4. Rapprochement avec les paiements
SELECT COALESCE(SUM(p.amount_cents), 0) AS total_paiements_encaisses
FROM payments p
JOIN orders o ON p.order_id = o.order_id
WHERE o.status = 'completed' AND p.status = 'captured';