SELECT
    i.offer_id,
    i.date_observation,
    i.supplier_id,
    i.product_id,
    i.sku,
    i.nom_produit,
    i.prix_achat_eur,
    i.prix_vente_eur,
    i.marge_unitaire_eur,
    CASE
        WHEN i.prix_vente_cents > 0
        THEN ROUND(((i.prix_vente_cents - i.prix_achat_cents)::numeric / i.prix_vente_cents) * 100, 1)
        ELSE 0
    END AS taux_marge_pct,
    i.stock_disponible,
    COALESCE(v.quantite_vendue, 0) AS quantite_vendue_historique,
    ROUND(COALESCE(v.ca_realise_cents, 0) / 100.0, 2) AS ca_realise_eur
FROM {{ ref('int_offres_enrichies') }} i
LEFT JOIN {{ ref('stg_ventes_produits') }} v
  ON v.product_id = i.product_id
ORDER BY i.product_id, i.date_observation