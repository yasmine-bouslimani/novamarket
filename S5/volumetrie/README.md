# S5 · Streaming Hugging Face, PySpark et Hub

## Installation à vérifier dès S4

Dans le venv Python 3.12 de S3, depuis `novamarket/` :

```bash
python -m pip install -r requirements-v3.txt -r volumetrie/requirements.txt
python --version
java -version
export JAVA_HOME=/chemin/vers/java21
export SPARK_LOCAL_IP=127.0.0.1
export PYSPARK_PYTHON="$(command -v python)"
export PYSPARK_SUBMIT_ARGS='--driver-memory 1g pyspark-shell'
python volumetrie/spark/verifier.py
HF_HUB_DISABLE_XET=1 python volumetrie/hf_datasets/acces.py
python volumetrie/hf_datasets/acces.py --infos
```

Utiliser une installation complète de Java 21. Sous Ubuntu/WSL2, utiliser le paquet OpenJDK 21 disponible sur le poste ou demander au formateur de le préparer. Spark tourne localement avec deux fils. Le diagnostic public ne nécessite aucun compte. Garder une version de Python dans le venv et la même pour les processus Spark.

## Source publique et parcours borné

[NYC TaxiData sur HF](https://huggingface.co/datasets/DinoPonjevic/NYC_TaxiData) reproduit et normalise des données publiques de transport. À la [révision retenue](https://huggingface.co/datasets/DinoPonjevic/NYC_TaxiData/tree/5941adbf8c0b9930e47002dc3103de3f9291360d), l'API de métadonnées liste **371 Parquet pour 39 350 805 895 octets**. Les fichiers sont organisés par année, type de taxi et mois. Le miroir indique `unknown` dans le champ licence. La source TLC est publiée sur NYC Open Data, dont les règles autorisent l'usage de ces données ouvertes. Utiliser le miroir pour lecture et analyse. Pour l'exercice de republication, employer seulement un jeu synthétique autorisé ou un agrégat validé par le formateur. La TLC indique ne pas collecter d'informations sur les passagers. [Source TLC](https://www.nyc.gov/site/tlc/about/raw-data.page) · [Conditions d'usage NYC Open Data](https://www.nyc.gov/opendata/get-started/FAQs)

Le diagnostic et le TP sélectionnent la partition Yellow de janvier 2024 épinglée dans `hf_datasets/source.json`. L'échantillon projeté contient `Start_Zone` (code zone), `Trip_Distance` (miles) et `Trip_Duration` (secondes). La taille du dépôt, la taille de la partition, le trafic et les lignes effectivement lues sont quatre mesures différentes. Utiliser `streaming=True`, parcourir progressivement, compter les lignes **avant** filtrage et écrire un sous-ensemble JSONL. Fermer explicitement l'itérateur dans un bloc `finally`; l'accès fourni désactive le préchargement Parquet et utilise des lots courts. Le [petit exemple de streaming](streaming/exemple.py) utilise des cuves.

## Pipeline Spark à développer

Lire l'extrait JSONL et la table de zones, contrôler le schéma, typer, projeter, filtrer et ajouter une colonne calculée. Contrôler la clé de la table de zones avant la jointure, identifier les lignes non appariées et comparer les volumes avant/après. Agréger, examiner le nombre de partitions et `explain()`, exporter en Parquet puis relire et vérifier. Choisir un dossier de sortie neuf pour chaque essai. L'[exemple indépendant](spark/exemple.py) se lance avec un chemin de sortie en argument. En cas d'indisponibilité distante, conserver le même schéma avec [le petit extrait fictif](secours/trajets_fictifs.jsonl). La [table de zones officielle TLC](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) est aussi fournie sous `secours/zones.csv`. Le secours permet Spark, la Dataset Card et l'essai Hub, et n'atteste pas le streaming distant.

## Publier deux révisions sur le Hub

Créer un token aux droits nécessaires sur son propre compte. Le saisir dans l'invite de `hf auth login`, puis vérifier `hf auth whoami`. Privilégier un dépôt privé. En cas de fuite, révoquer le token dans les réglages du Hub, exécuter `hf auth logout` et créer un autre token. Ne journaliser ni le token ni un fichier d'authentification. Un refus 401 appelle une vérification de connexion, un refus 403 des permissions et de l'espace de noms.

Préparer un dossier de publication distinct avec **uniquement** `README.md` à partir du [modèle de Dataset Card](documentation/DATASET_CARD_MODELE.md) et un fichier de données autorisé. Définir `repo` comme `votre-compte/nom-de-depot`. Vérifier le contenu avant chacune des commandes :

```bash
hf auth login
hf auth whoami
hf repo create "$repo" --repo-type dataset --private
hf upload "$repo" ./publication . --repo-type dataset --commit-message "v1 : premier jeu vérifié"
# Modifier une donnée autorisée ou l'extraction et documenter la modification dans README.md.
hf upload "$repo" ./publication . --repo-type dataset --commit-message "v2 : changement documenté"
# Consigner les deux SHA affichés par le Hub, puis vérifier la première version.
hf download "$repo" README.md --repo-type dataset --revision "$sha_v1"
hf download "$repo" README.md --repo-type dataset --revision "$sha_v2"
```

Comparer aussi le Parquet aux deux révisions en remplaçant le nom du fichier à télécharger. Conserver des preuves sans token. En cas de compte indisponible, réaliser la préparation locale et solliciter un accès autorisé pour le passage Hub. La branche analytique S6 peut commencer pendant ce rattrapage. [CLI officielle](https://huggingface.co/docs/huggingface_hub/guides/cli) · [Sécurité des tokens](https://huggingface.co/docs/hub/security-tokens) · [Installation PySpark 4.1.1](https://spark.apache.org/docs/4.1.1/api/python/getting_started/install.html)
