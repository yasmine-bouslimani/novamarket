SELECT
    o.offer_id,
    o.date_observation,
    o.supplier_id,
    o.product_id,
    p.sku,
    p.nom_produit,
    o.prix_achat_cents,
    o.prix_achat_eur,
    p.prix_vente_cents,
    p.prix_vente_eur,
    (p.prix_vente_cents - o.prix_achat_cents) AS marge_unitaire_cents,
    ROUND((p.prix_vente_cents - o.prix_achat_cents) / 100.0, 2) AS marge_unitaire_eur,
    o.stock_disponible
FROM {{ ref('stg_offres') }} o
JOIN {{ ref('stg_products') }} p
  ON p.product_id = o.product_id