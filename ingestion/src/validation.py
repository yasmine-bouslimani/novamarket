"""Point de départ du groupe. Implémenter les contrôles et motifs de rejet ici."""


"""Contrôles structurels, règles métier et détection de doublons."""
from datetime import date

CHAMPS_REQUIS = {
    "offer_id",
    "supplier_id",
    "product_id",
    "price_cents",
    "currency",
    "available_units",
    "observed_on",
}
FOURNISSEURS_VALIDES = {"F01", "F02", "F03"}
CATALOGUE_PRODUITS_S2 = set(range(1, 25))  # 24 produits du catalogue S2


def valider_offre(offre: dict, ids_deja_vus: set[str]) -> tuple[bool, str | None]:
    """Retourne (True, None) si conforme, sinon (False, motif_rejet)."""
    if not isinstance(offre, dict):
        return False, "format_non_objet"

    # 1. Champs requis et non vides
    manquants = CHAMPS_REQUIS - set(offre.keys())
    if manquants:
        return False, f"champs_manquants:{','.join(sorted(manquants))}"

    for champ in CHAMPS_REQUIS:
        if offre[champ] is None or offre[champ] == "":
            return False, f"champ_vide:{champ}"

    # 2. Validation des types (exclut les booléens qui héritent de int en Python)
    if not isinstance(offre["offer_id"], str) or not isinstance(offre["supplier_id"], str):
        return False, "type_identifiant_invalide"
    if type(offre["product_id"]) is not int:
        return False, "type_product_id_invalide"
    if type(offre["price_cents"]) is not int:
        return False, "type_price_cents_invalide"
    if type(offre["available_units"]) is not int:
        return False, "type_available_units_invalide"

    # 3. Règles métier et catalogue S2
    if offre["supplier_id"] not in FOURNISSEURS_VALIDES:
        return False, f"fournisseur_inconnu:{offre['supplier_id']}"
    if offre["product_id"] not in CATALOGUE_PRODUITS_S2:
        return False, f"product_id_hors_catalogue:{offre['product_id']}"
    if offre["price_cents"] < 0 or offre["available_units"] < 0:
        return False, "valeur_negative"
    if offre["currency"] != "EUR":
        return False, f"devise_invalide:{offre['currency']}"

    try:
        date.fromisoformat(str(offre["observed_on"]))
    except ValueError:
        return False, f"date_invalide:{offre['observed_on']}"

    # 4. Unicité de la clé métier offer_id
    offer_id = offre["offer_id"]
    if offer_id in ids_deja_vus:
        return False, f"doublon_offer_id:{offer_id}"

    ids_deja_vus.add(offer_id)
    return True, None
