
"""Point de départ du groupe. Implémenter le journal et le bilan de collecte ici."""

"""Journalisation structurée, écriture JSONL UTF-8 et bilan de collecte."""
from dataclasses import dataclass, field
import json
import logging
from pathlib import Path


@dataclass
class BilanCollecte:
    scenario: str
    run: str
    pages_attendues: int = 0
    pages_recues: int = 0
    requetes_http: int = 0
    retries: int = 0
    lignes_examinees: int = 0
    lignes_valides: int = 0
    lignes_rejetees: int = 0
    duree_secondes: float = 0.0
    statut: str = "en_cours"
    erreurs_pages: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "statut": self.statut,
            "scenario": self.scenario,
            "run": self.run,
            "pages_attendues": self.pages_attendues,
            "pages_recues": self.pages_recues,
            "requetes_http": self.requetes_http,
            "retries": self.retries,
            "lignes_examinees": self.lignes_examinees,
            "lignes_valides": self.lignes_valides,
            "lignes_rejetees": self.lignes_rejetees,
            "duree_secondes": round(self.duree_secondes, 3),
            "erreurs_pages": self.erreurs_pages,
        }


def ecrire_jsonl(chemin: Path, enregistrements: list[dict]) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8") as f:
        for obj in enregistrements:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def publier_resultats(
    base_dir: Path,
    bilan: BilanCollecte,
    pages_brutes: list[dict],
    offres_valides: list[dict],
    rejets: list[dict],
) -> None:
    """Écrit raw/, rejected/ et le bilan. Ne publie valid/offres.jsonl que si le lot est complet."""
    logger = logging.getLogger("novamarket.ingestion")

    ecrire_jsonl(base_dir / "data" / "raw" / f"raw_{bilan.scenario}_{bilan.run}.jsonl", pages_brutes)
    ecrire_jsonl(base_dir / "data" / "rejected" / f"rejets_{bilan.scenario}_{bilan.run}.jsonl", rejets)

    fichier_valid = base_dir / "data" / "valid" / "offres.jsonl"

    if bilan.statut != "succes" or bilan.pages_recues != bilan.pages_attendues:
        logger.error(
            "Lot incomplet (%s/%s pages) : publication de %s annulée.",
            bilan.pages_recues,
            bilan.pages_attendues,
            fichier_valid,
        )
    else:
        ecrire_jsonl(fichier_valid, offres_valides)
        logger.info("Publication réussie : %s offres dans %s", len(offres_valides), fichier_valid)

    bilan_path = base_dir / "data" / f"bilan_{bilan.scenario}_{bilan.run}.json"
    bilan_path.parent.mkdir(parents=True, exist_ok=True)
    bilan_path.write_text(json.dumps(bilan.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")