"""Parcourir trois mesures de cuve sans matérialiser toutes les lignes."""
from datasets import IterableDataset


def mesures():
    for id_cuve, litres in enumerate((15, 25, 33, 42, 44), 1):
        yield {"cuve": id_cuve, "litres": litres}


flux = IterableDataset.from_generator(mesures)
for mesure in flux.take(3):
    print(mesure)
