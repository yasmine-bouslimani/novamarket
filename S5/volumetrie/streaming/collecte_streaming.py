"""Missions M2 & M3 : Lecture en streaming bornée sur HF Datasets, filtrage et export JSONL."""
import argparse
from itertools import islice
import json
from pathlib import Path
import sys

RACINE_VOLUMETRIE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE_VOLUMETRIE / "hf_datasets"))

from acces import SOURCE, ouvrir  # noqa: E402


def valider_et_nettoyer(ligne: dict) -> tuple[dict | None, str | None]:
    """Vérifie la présence, les types et la cohérence physique d'un trajet."""
    if not isinstance(ligne, dict):
        return None, "format_invalide"

    zone = ligne.get("Start_Zone")
    dist = ligne.get("Trip_Distance")
    duree = ligne.get("Trip_Duration")

    if zone is None or dist is None or duree is None:
        return None, "valeur_manquante"

    try:
        zone_int = int(zone)
        dist_float = float(dist)
        duree_float = float(duree)
    except (TypeError, ValueError):
        return None, "type_invalide"

    if zone_int <= 0:
        return None, f"zone_invalide:{zone_int}"
    if dist_float <= 0 or dist_float > 500:
        return None, f"distance_incoherente:{dist_float}"
    if duree_float <= 0 or duree_float > 86400:
        return None, f"duree_incoherente:{duree_float}"

    return {
        "Start_Zone": zone_int,
        "Trip_Distance": round(dist_float, 3),
        "Trip_Duration": round(duree_float, 1),
    }, None


def executer_streaming(limite: int, sortie_jsonl: Path, fichier_secours: Path | None = None) -> dict:
    sortie_jsonl.parent.mkdir(parents=True, exist_ok=True)
    bilan = {
        "source_repo": SOURCE["repo"],
        "source_revision": SOURCE["revision"],
        "partition": SOURCE["shard"],
        "mode": "secours_local" if fichier_secours else "streaming_huggingface",
        "limite_demandee": limite,
        "lignes_parcourues": 0,
        "lignes_retenues": 0,
        "lignes_rejetees": 0,
        "motifs_rejet": {},
        "fichier_sortie": str(sortie_jsonl),
    }

    if fichier_secours:
        def iterateur_secours():
            with fichier_secours.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        yield json.loads(line)
        flux = iterateur_secours()
    else:
        flux = iter(ouvrir())

    try:
        with sortie_jsonl.open("w", encoding="utf-8") as out:
            for brute in islice(flux, limite):
                bilan["lignes_parcourues"] += 1
                propre, motif = valider_et_nettoyer(brute)
                if motif is not None:
                    bilan["lignes_rejetees"] += 1
                    bilan["motifs_rejet"][motif] = bilan["motifs_rejet"].get(motif, 0) + 1
                    continue

                bilan["lignes_retenues"] += 1
                out.write(json.dumps(propre, ensure_ascii=False) + "\n")
    finally:
        if hasattr(flux, "close"):
            flux.close()

    bilan["octets_ecrits"] = sortie_jsonl.stat().st_size if sortie_jsonl.exists() else 0
    return bilan


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extraction streaming bornée NYC TaxiData")
    parser.add_argument("--limite", type=int, default=500, help="Nombre maximal de lignes parcourues")
    parser.add_argument(
        "--sortie",
        type=Path,
        default=RACINE_VOLUMETRIE / "sorties" / "trajets_valides.jsonl",
    )
    parser.add_argument(
        "--secours",
        action="store_true",
        help="Utilise volumetrie/secours/trajets_fictifs.jsonl si le réseau HF est bloqué",
    )
    args = parser.parse_args()

    secours_path = (RACINE_VOLUMETRIE / "secours" / "trajets_fictifs.jsonl") if args.secours else None
    rapport = executer_streaming(args.limite, args.sortie, secours_path)

    rapport_path = args.sortie.with_name("bilan_streaming.json")
    rapport_path.write_text(json.dumps(rapport, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(rapport, indent=2, ensure_ascii=False))