SELECT
    product_id,
    sku,
    product_name AS nom_produit,
    category_id,
    unit_price_cents AS prix_vente_cents,
    ROUND(unit_price_cents / 100.0, 2) AS prix_vente_eur,
    is_active AS est_actif
FROM {{ source('novamarket_core', 'products') }}