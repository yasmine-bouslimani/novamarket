"""Chargeur PostgreSQL transactionnel et idempotent pour les offres fournisseurs (S4 - M1)."""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys

import psycopg

FOURNISSEURS_VALIDES = {"F01", "F02", "F03"}
CHAMPS_REQUIS = {
    "offer_id",
    "supplier_id",
    "product_id",
    "price_cents",
    "currency",
    "available_units",
    "observed_on",
}

DDL_INITIALISATION = """
CREATE SCHEMA IF NOT EXISTS fournisseurs;

CREATE TABLE IF NOT EXISTS fournisseurs.offres_observees (
    offer_id        text        NOT NULL,
    supplier_id     text        NOT NULL,
    product_id      integer     NOT NULL,
    price_cents     integer     NOT NULL CHECK (price_cents >= 0),
    currency        char(3)     NOT NULL CHECK (currency = 'EUR'),
    available_units integer     NOT NULL CHECK (available_units >= 0),
    observed_on     date        NOT NULL,
    loaded_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (offer_id, observed_on)
);
"""

SQL_UPSERT = """
INSERT INTO fournisseurs.offres_observees (
    offer_id, supplier_id, product_id, price_cents, currency, available_units, observed_on
)
VALUES (%(offer_id)s, %(supplier_id)s, %(product_id)s, %(price_cents)s, %(currency)s, %(available_units)s, %(observed_on)s)
ON CONFLICT (offer_id, observed_on) DO UPDATE SET
    supplier_id     = EXCLUDED.supplier_id,
    product_id      = EXCLUDED.product_id,
    price_cents     = EXCLUDED.price_cents,
    currency        = EXCLUDED.currency,
    available_units = EXCLUDED.available_units,
    loaded_at       = now()
WHERE (
    fournisseurs.offres_observees.supplier_id,
    fournisseurs.offres_observees.product_id,
    fournisseurs.offres_observees.price_cents,
    fournisseurs.offres_observees.currency,
    fournisseurs.offres_observees.available_units
) IS DISTINCT FROM (
    EXCLUDED.supplier_id,
    EXCLUDED.product_id,
    EXCLUDED.price_cents,
    EXCLUDED.currency,
    EXCLUDED.available_units
)
RETURNING (xmax = 0) AS est_insertion;
"""


def controler_et_convertir(ligne: dict, produits_catalogue: set[int]) -> tuple[dict | None, str | None]:
    """Valide les types, dates, devise, fournisseur et référence catalogue S2."""
    if not isinstance(ligne, dict):
        return None, "format_non_objet"

    manquants = CHAMPS_REQUIS - set(ligne.keys())
    if manquants:
        return None, f"champs_manquants:{','.join(sorted(manquants))}"

    if type(ligne["product_id"]) is not int or type(ligne["price_cents"]) is not int or type(ligne["available_units"]) is not int:
        return None, "type_numerique_invalide"

    if ligne["supplier_id"] not in FOURNISSEURS_VALIDES:
        return None, f"fournisseur_inconnu:{ligne['supplier_id']}"

    if ligne["product_id"] not in produits_catalogue:
        return None, f"product_id_hors_catalogue:{ligne['product_id']}"

    if ligne["price_cents"] < 0 or ligne["available_units"] < 0:
        return None, "valeur_negative"

    if ligne["currency"] != "EUR":
        return None, f"devise_invalide:{ligne['currency']}"

    try:
        date_obs = date.fromisoformat(str(ligne["observed_on"]))
    except ValueError:
        return None, f"date_invalide:{ligne['observed_on']}"

    return {
        "offer_id": str(ligne["offer_id"]).strip(),
        "supplier_id": str(ligne["supplier_id"]).strip(),
        "product_id": ligne["product_id"],
        "price_cents": ligne["price_cents"],
        "currency": "EUR",
        "available_units": ligne["available_units"],
        "observed_on": date_obs,
    }, None


def charger_catalogue_produits(cur: psycopg.Cursor) -> set[int]:
    """Récupère les product_id existants dans public.products (S2), ou 1..24 par défaut."""
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'products'
        )
    """)
    if cur.fetchone()[0]:
        cur.execute("SELECT product_id FROM public.products")
        return {row[0] for row in cur.fetchall()}
    return set(range(1, 25))


def charger_jsonl(chemin_fichier: Path, strict: bool = False) -> dict:
    dsn = os.environ.get("NOVAMARKET_DSN")
    if not dsn:
        raise RuntimeError("La variable d'environnement NOVAMARKET_DSN est absente.")

    if not chemin_fichier.exists():
        raise FileNotFoundError(f"Fichier JSONL introuvable : {chemin_fichier}")

    bilan = {
        "fichier": str(chemin_fichier),
        "statut": "en_cours",
        "lignes_lues": 0,
        "inserees": 0,
        "mises_a_jour": 0,
        "inchangees": 0,
        "rejetees": 0,
        "details_rejets": [],
    }

    with psycopg.connect(dsn, connect_timeout=5) as conn:
        # Transaction unique : tout le lot est validé ensemble ou annulé (ROLLBACK)
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(DDL_INITIALISATION)
                produits_valides = charger_catalogue_produits(cur)

                with chemin_fichier.open("r", encoding="utf-8") as f:
                    for num_ligne, brut in enumerate(f, start=1):
                        brut = brut.strip()
                        if not brut:
                            continue
                        bilan["lignes_lues"] += 1

                        try:
                            objet = json.loads(brut)
                        except json.JSONDecodeError as exc:
                            motif = f"json_invalide:{exc}"
                            bilan["rejetees"] += 1
                            bilan["details_rejets"].append({"ligne": num_ligne, "motif": motif})
                            if strict:
                                raise ValueError(f"Erreur ligne {num_ligne} : {motif}") from exc
                            continue

                        propre, motif = controler_et_convertir(objet, produits_valides)
                        if motif is not None:
                            bilan["rejetees"] += 1
                            bilan["details_rejets"].append({"ligne": num_ligne, "motif": motif, "brut": objet})
                            if strict:
                                raise ValueError(f"Erreur ligne {num_ligne} : {motif}")
                            continue

                        cur.execute(SQL_UPSERT, propre)
                        res = cur.fetchone()
                        if res is None:
                            bilan["inchangees"] += 1
                        elif res[0]:
                            bilan["inserees"] += 1
                        else:
                            bilan["mises_a_jour"] += 1

        bilan["statut"] = "succes"
    return bilan


if __name__ == "__main__":
    racine = Path(__file__).resolve().parents[1]
    defaut_s3 = racine / "ingestion" / "data" / "valid" / "offres.jsonl"
    secours_s4 = racine / "transformation" / "secours" / "offres.jsonl"
    fichier_defaut = defaut_s3 if defaut_s3.exists() else secours_s4

    parser = argparse.ArgumentParser(description="Chargement PostgreSQL des offres fournisseurs")
    parser.add_argument("--fichier", type=Path, default=fichier_defaut)
    parser.add_argument("--strict", action="store_true", help="Annule toute la transaction au moindre rejet")
    args = parser.parse_args()

    try:
        resultat = charger_jsonl(args.fichier, strict=args.strict)
        print(json.dumps(resultat, indent=2, ensure_ascii=False))
    except Exception as err:
        print(f"[ERREUR TRANSACTIONNELLE - ROLLBACK EFFECTUÉ] {err}", file=sys.stderr)
        sys.exit(1)