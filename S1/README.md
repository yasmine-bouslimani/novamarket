# Livrable NovaMarket S1

## M1 : Modélisation et Grains des sources
- **Grains et relations 1–N :**
  - `customers.csv` : 1 ligne = 1 client unique (`customer_id`).
  - `orders.csv` : 1 ligne = 1 commande (`order_id`). Relation 1–N : 1 client possède N commandes.
  - `order_items.csv` : 1 ligne = 1 ligne d'article (`order_item_id`). Relation 1–N : 1 commande possède N articles.
  - `payments.ndjson` : 1 ligne = 1 opération de paiement (`payment_id`). Relation 1–N : 1 commande possède N paiements.
- **Choix de conception :**
  1. Utilisation de l'entier (`integer`) pour les montants en centimes afin d'éviter les erreurs d'arrondi des nombres flottants.
  2. Sécurisation des statuts (`completed`, `pending`, `cancelled` / `captured`) directement via des contraintes `CHECK` sensibles à la casse, évitant des jointures inutiles et bloquant toute erreur de saisie.

## M2 : Qualité et Intégration
- **Volumes :** 180 clients, 400 commandes et 480 paiements reçus et intégrés (0 rejet).
- **Journal des rejets (`order_items.csv`) :** Sur 802 lignes reçues, 800 ont été intégrées et 2 écartées :
  - **1 doublon strict :** La ligne `order_item_id = 7` (commande 4) était présente en double ; fusionnée via `SELECT DISTINCT`.
  - **1 référence orpheline :** La ligne `order_item_id = 801` pointait vers la commande inexistante `order_id = 9999` ; rejetée par filtrage référentiel pour préserver la clé étrangère.

## M3 : Résultats des indicateurs
- **Clients sans commande :** 30 clients.
- **Répartition des commandes :** 320 `completed`, 40 `pending`, 40 `cancelled`.
- **CA Total (commandes terminées) :** 26 210,00 € (2 621 000 centimes).
- **Panier Moyen :** 81,91 € (8 190,63 centimes — dénominateur explicite : les 320 commandes terminées).
- **Rapprochement des paiements :** Le total des paiements encaissés (`captured`) sur les commandes terminées s'élève à 26 210,00 € (2 621 000 centimes). L'écart avec le CA facturé est de 0, ce qui valide la cohérence entre les grains.

## M4 : Tableau d'investigation des anomalies

| Anomalie | Détection (SQL) | Risque et Effet Métier | Action et Décision |
|---|---|---|---|
| Doublon de ligne (`id=7`) | `GROUP BY order_item_id HAVING COUNT(*) > 1` | Gonfle artificiellement le CA et les quantités vendues. | Dédoublonnage via `SELECT DISTINCT` à l'insertion. |
| Référence orpheline (`cmd=9999`) | `LEFT JOIN orders o ON oi.order_id = o.order_id WHERE o.order_id IS NULL` | CA "fantôme" non attribuable à un client ; violation de clé étrangère. | Filtrage restrictif via `WHERE order_id IN (SELECT order_id FROM orders)`. |
| Multiplication par jointure | Jointure directe `orders` + `order_items` + `payments` | Si 1 commande a 3 articles et 2 paiements, la jointure génère 6 lignes et multiplie les montants. | Agréger (`SUM`) dans une CTE (`WITH`) par grain *avant* de joindre. |
| Statut non filtré | Omission de `WHERE o.status = 'completed'` | Intègre des commandes en attente ou annulées dans le CA réalisé. | Toujours filtrer sur `status = 'completed'` pour le CA réalisé. |

## M5 : État du projet et exécution
- **Structure du dépôt (`s1/`) :**
  - `import.sql` : Création des tables temporaires de réception, DDL du schéma cible et intégration filtrée.
  - `indicateurs.sql` : Requêtes SQL reproductibles des indicateurs commerciaux et de rapprochement.
  - `README.md` : Documentation, audit des rejets et preuves.
- **Exécution :** Lancer `psql` sur la base `novamarket` puis exécuter `\i s1/import.sql` suivi de `\i s1/indicateurs.sql`.
- **Limites identifiées :** Le catalogue produits (`product_id`) et les devises autres que l'euro sont hors périmètre S1.

## A1 : Variantes et Normalisation
- **Anomalies sur `planning_a_normaliser.csv` (table redondante) :**
  - *Insertion :* Impossible d'enregistrer une nouvelle salle sans créer une réservation fictive.
  - *Mise à jour :* Changer le responsable d'une salle oblige à modifier toutes ses lignes de réservation (risque d'incohérence).
  - *Suppression :* Supprimer la dernière réservation d'une salle efface l'existence même de la salle et de son responsable.
  - *Solution :* Normalisation en 3NF en séparant `salles` et `reservations` via une clé étrangère `salle_id`.
- **Test d'une autre stratégie de jointure :**
  - Un `LEFT JOIN` direct depuis `orders` vers `payments` fonctionne tant qu'on ne joint pas `order_items` en même temps (sinon produit cartésien partiel qui duplique les paiements).
  - *Alternative retenue :* Pré-agrégation via une CTE (`WITH`) ou utilisation d'un `LEFT JOIN LATERAL` pour isoler le calcul par commande avant toute jointure multi-grains.
  