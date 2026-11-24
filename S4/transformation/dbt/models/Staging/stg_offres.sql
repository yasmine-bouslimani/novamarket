SELECT
    offer_id,
    supplier_id,
    product_id,
    price_cents AS prix_achat_cents,
    ROUND(price_cents / 100.0, 2) AS prix_achat_eur,
    currency AS devise,
    available_units AS stock_disponible,
    observed_on AS date_observation
FROM {{ source('fournisseurs', 'offres_observees') }}