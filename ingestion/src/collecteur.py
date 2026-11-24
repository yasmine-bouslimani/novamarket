

"""Collecteur asynchrone paginé, concurrent et résilient pour l'API NovaMarket."""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import time

import aiohttp

from journalisation import BilanCollecte, publier_resultats
from validation import valider_offre

logger = logging.getLogger("novamarket.ingestion")


class ErreurTransitoire(Exception):
    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class ErreurPermanente(Exception):
    pass


async def recuperer_page(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    base_url: str,
    page: int,
    scenario: str,
    run: str,
    bilan: BilanCollecte,
    max_essais: int = 3,
) -> dict:
    url = f"{base_url}/offers"
    params = {"page": page, "scenario": scenario, "run": run}

    for essai in range(1, max_essais + 1):
        try:
            async with semaphore:
                bilan.requetes_http += 1
                async with session.get(url, params=params) as resp:
                    if resp.status == 429:
                        ra = resp.headers.get("Retry-After")
                        delai = float(ra) if ra and ra.isdigit() else 0.5 * essai
                        raise ErreurTransitoire(f"HTTP 429 sur page {page}", retry_after=delai)

                    if resp.status in (500, 502, 503, 504):
                        raise ErreurTransitoire(f"HTTP {resp.status} sur page {page}")

                    if 400 <= resp.status < 500:
                        raise ErreurPermanente(f"HTTP {resp.status} non récupérable sur page {page}")

                    texte = await resp.text()
                    try:
                        payload = json.loads(texte)
                    except json.JSONDecodeError as exc:
                        raise ErreurTransitoire(f"JSON invalide sur page {page}: {exc}") from exc

                    if not isinstance(payload, dict) or "items" not in payload:
                        raise ErreurTransitoire(f"Structure de réponse inattendue sur page {page}")

                    logger.info("Page %s récupérée (essai %s/%s)", page, essai, max_essais)
                    return payload

        except (asyncio.TimeoutError, aiohttp.ClientError, ErreurTransitoire) as exc:
            if essai == max_essais:
                logger.error("Échec définitif page %s après %s essais : %s", page, max_essais, exc)
                raise
            bilan.retries += 1
            attente = getattr(exc, "retry_after", None) or (0.3 * essai)
            logger.warning("Reprise page %s (essai %s/%s) dans %.2fs : %s", page, essai, max_essais, attente, exc)
            await asyncio.sleep(attente)


async def executer_collecte(scenario: str, run: str, max_concurrence: int, timeout_sec: float) -> BilanCollecte:
    debut = time.perf_counter()
    port = int(os.environ.get("NOVAMARKET_API_PORT", "18080"))
    base_url = f"http://127.0.0.1:{port}"
    base_dir = Path(__file__).resolve().parents[1]

    bilan = BilanCollecte(scenario=scenario, run=run)
    semaphore = asyncio.Semaphore(max_concurrence)
    timeout = aiohttp.ClientTimeout(total=timeout_sec)

    pages_brutes: list[dict] = []
    offres_valides: list[dict] = []
    rejets: list[dict] = []
    ids_vus: set[str] = set()

    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            # Page 1 : découverte dynamique du nombre total de pages
            p1 = await recuperer_page(session, semaphore, base_url, 1, scenario, run, bilan)
            total_pages = int(p1["total_pages"])
            bilan.pages_attendues = total_pages
            resultats_pages = {1: p1}

            # Pages 2..N : exécution concurrente bornée par Semaphore
            if total_pages > 1:
                taches = [
                    recuperer_page(session, semaphore, base_url, p, scenario, run, bilan)
                    for p in range(2, total_pages + 1)
                ]
                autres = await asyncio.gather(*taches)
                for payload in autres:
                    resultats_pages[int(payload["page"])] = payload

            # Validation dans l'ordre déterministe des pages
            for num_page in range(1, total_pages + 1):
                payload = resultats_pages[num_page]
                bilan.pages_recues += 1
                pages_brutes.append(payload)

                for pos, item in enumerate(payload.get("items", []), start=1):
                    bilan.lignes_examinees += 1
                    ok, motif = valider_offre(item, ids_vus)
                    if ok:
                        offres_valides.append(item)
                        bilan.lignes_valides += 1
                    else:
                        rejets.append({
                            "page": num_page,
                            "position": pos,
                            "motif": motif,
                            "objet_brut": item,
                        })
                        bilan.lignes_rejetees += 1

            bilan.statut = "succes"

        except Exception as exc:
            bilan.statut = "echec"
            bilan.erreurs_pages.append({"erreur": str(exc)})
            logger.error("Collecte interrompue (%s) : %s", scenario, exc)

    bilan.duree_secondes = time.perf_counter() - debut
    publier_resultats(base_dir, bilan, pages_brutes, offres_valides, rejets)
    print(json.dumps(bilan.to_dict(), indent=2, ensure_ascii=False))
    return bilan


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Collecteur asynchrone NovaMarket")
    parser.add_argument("--scenario", default="atelier", choices=["clean", "atelier", "panne"])
    parser.add_argument("--run", default="groupe01-essai01")
    parser.add_argument("--concurrence", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=1.0)
    args = parser.parse_args()

    asyncio.run(executer_collecte(args.scenario, args.run, args.concurrence, args.timeout))
