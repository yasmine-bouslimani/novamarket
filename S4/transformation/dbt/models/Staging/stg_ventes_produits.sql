SELECT
    oi.product_id,
    COUNT(DISTINCT o.order_id) AS nb_commandes_completed,
    COALESCE(SUM(oi.quantity), 0) AS quantite_vendue,
    COALESCE(SUM(oi.quantity * oi.unit_price_cents), 0) AS ca_realise_cents
FROM {{ source('novamarket_core', 'order_items') }} oi
JOIN {{ source('novamarket_core', 'orders') }} o
  ON o.order_id = oi.order_id
WHERE o.status = 'completed'
GROUP BY oi.product_id