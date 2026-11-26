"""Accès borné à une partition publiée du dataset réel."""
import argparse
import json
from pathlib import Path

import aiohttp
import pyarrow.dataset as pq
from datasets import load_dataset
from huggingface_hub import HfApi

SOURCE = json.loads(Path(__file__).with_name("source.json").read_text(encoding="utf-8"))


def ouvrir():
    url = f"https://huggingface.co/datasets/{SOURCE['repo']}/resolve/{SOURCE['revision']}/{SOURCE['shard']}"
    return load_dataset("parquet", data_files={"train": url}, split="train", streaming=True,
                        columns=SOURCE["columns"], batch_size=128,
                        fragment_scan_options=pq.ParquetFragmentScanOptions(pre_buffer=False),
                        storage_options={"client_kwargs": {"timeout": aiohttp.ClientTimeout(total=30)}})


def verifier_metadata():
    info = HfApi().dataset_info(SOURCE["repo"], revision=SOURCE["revision"], files_metadata=True, token=False)
    files = {entry.rfilename: entry.size for entry in info.siblings if entry.rfilename.endswith(".parquet")}
    size = sum(files.values())
    assert info.sha == SOURCE["revision"] and len(files) == SOURCE["parquet_files"]
    assert size == SOURCE["parquet_bytes"] and size > 10_000_000_000
    print(json.dumps(dict(revision=info.sha, parquet=len(files), octets=size,
                          taille_partition=files[SOURCE["shard"]],
                          licence_miroir=info.card_data.license)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--infos", action="store_true", help="Contrôler les métadonnées du dépôt sans streaming")
    if parser.parse_args().infos:
        verifier_metadata()
        raise SystemExit(0)
    flux = iter(ouvrir())
    try:
        ligne = next(flux)
        assert set(ligne) == set(SOURCE["columns"])
        print("Streaming accessible ; colonnes :", ", ".join(ligne))
    finally:
        flux.close()
