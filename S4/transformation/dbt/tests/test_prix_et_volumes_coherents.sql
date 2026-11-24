-- Vérifie qu'aucune offre dans le mart n'a un prix d'achat nul/négatif ou une date manquante.
-- Ce test réussit s'il retourne 0 ligne.
SELECT
    offer_id,
    date_observation,
    prix_achat_eur,
    prix_vente_eur
FROM {{ ref('mart_comparaison_offres') }}
WHERE prix_achat_eur <= 0
   OR prix_vente_eur <= 0
   OR date_observation IS NULL