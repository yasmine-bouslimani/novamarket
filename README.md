# Livrable NovaMarket S1

## M1 & M2 : Qualité et Intégration
- **Volume :** 180 clients, 400 commandes, 480 paiements intégrés (0 rejet).
- **Anomalies écartées :** Sur 802 lignes de `order_items.csv`, 800 ont été intégrées. 
  - 1 ligne doublon stricte fusionnée via `DISTINCT`.
  - 1 référence orpheline (item lié à la commande 9999 inexistante) rejetée pour préserver l'intégrité de la clé étrangère.
- **Choix de conception :**
  1. Utilisation de l'entier (`integer`) pour les centimes afin d'éviter les erreurs d'arrondis des flottants.
  2. Sécurisation des statuts (ex: pending, completed) directement avec des contraintes `CHECK` au lieu de tables de jointure, pour garantir 0 erreur de saisie.

## M3 : Résultats des indicateurs
- **Clients sans commande :** 30.
- **Répartition des commandes :** 320 terminées, 40 en attente, 40 annulées.
- **CA Total (commandes terminées) :** 26 210,00 € (2 621 000 centimes).
- **Panier Moyen :** 81,91 € (dénominateur : 320 commandes).
- **Rapprochement :** Le total des encaissements sur ces commandes est exactement de 26 210,00 €. L'écart est de 0, ce qui valide la structure.

## M4 : Tableau d'investigation des anomalies

| Anomalie | Risque et Effet Métier | Action et Décision |
|---|---|---|
| Doublon de ligne (`id=7`) | Gonfle artificiellement le CA et les quantités vendues. | Dédoublonnage via `DISTINCT` à l'insertion. |
| Référence orpheline (`cmd=9999`) | CA "fantôme" non attribuable à un client. Plante la BD. | Filtrage restrictif via `WHERE order_id IN (...)`. |
| Multiplication par jointure | Si 1 commande a 3 articles et 2 paiements, une jointure brute génère 6 lignes (CA faussé). | Agréger (SUM) dans une sous-requête (WITH) AVANT de faire la jointure. |
| Statut non filtré | Intègre des commandes annulées dans le Bilan Financier. | Toujours imposer `WHERE status = 'completed'`. |

## A1 : Variantes et Normalisation (Exemple Salle)
Le fichier non normalisé de l'atelier de démarrage présente de graves défauts de conception :
- **Anomalie d'insertion :** On ne peut pas insérer une nouvelle salle sans inventer une réservation associée.
- **Anomalie de modification :** Si le responsable change, il faut modifier N lignes. Un oubli détruit l'intégrité des données.
- **Anomalie de suppression :** Supprimer la dernière réservation d'une salle efface l'existence même de la salle.
- **Solution :** Passer en 3e Forme Normale en scindant Salles et Réservations (clés primaires/étrangères).


**Test d'une autre stratégie de jointure (A1) :**
Pour calculer le total des paiements d'une commande, on pourrait faire un `LEFT JOIN` direct depuis `orders` vers `payments`, puis un `SUM(amount_cents)`. 
- *Différence / Problème :* Si on fait un `LEFT JOIN` global incluant aussi `order_items`, le montant du paiement est dupliqué autant de fois qu'il y a d'articles dans la commande (produit cartésien partiel).
- *Solution retenue :* Agréger les paiements dans une sous-requête (CTE `WITH`) *avant* de faire la jointure, ou utiliser un `LEFT JOIN LATERAL` pour forcer l'agrégation par ligne de commande.