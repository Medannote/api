# Documentation de l'API Médicale Unifiée

## Introduction

Cette documentation fournit un guide complet pour l'utilisation de l'API, développée avec FastAPI. Cette API est conçue pour faciliter l'annotation de différents types de données médicales, notamment les images DICOM, les signaux physiologiques (format WFDB) et les rapports textuels. Elle offre des fonctionnalités d'anonymisation, de prétraitement, d'extraction de métadonnées et de génération d'annotations, essentielles pour la recherche médicale et les applications cliniques.

La documentation est structurée pour couvrir tous les aspects de l'API, depuis son lancement et son accès, jusqu'à l'utilisation détaillée de chaque endpoint disponible, en passant par les méthodes de test et la gestion des erreurs. Chaque section est conçue pour être claire et informative, avec des exemples pratiques pour vous aider à démarrer rapidement.




## Configuration et Lancement de l'API


### Prérequis

Avant de pouvoir lancer l'API, assurez-vous que les éléments suivants sont installés sur votre machine :

*   **Python 3.8+** : L'API est développée en Python. Il est recommandé d'utiliser une version récente de Python.
*   **pip** : Le gestionnaire de paquets Python, généralement inclus avec Python.

### Installation des Dépendances

Les dépendances de l'API sont listées dans le fichier `requirements.txt`. Pour les installer, naviguez jusqu'au répertoire racine du projet API dans votre terminal et exécutez la commande suivante :

```bash
pip install -r requirements.txt
```

Cette commande installera toutes les bibliothèques Python nécessaires, telles que FastAPI, Uvicorn, pydicom, nibabel, pandas, scikit-image, wfdb, python-docx, et nltk.

### Lancement du Serveur API

L'API est construite avec FastAPI et utilise Uvicorn comme serveur ASGI. Pour lancer l'API, assurez-vous d'être dans le répertoire racine du projet et exécutez la commande suivante :

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

*   `app.main:app` : Indique à Uvicorn de trouver l'application FastAPI nommée `app` dans le fichier `main.py`.
*   `--host 0.0.0.0` : Rend l'API accessible depuis toutes les interfaces réseau. Pour un usage local uniquement, vous pouvez utiliser `127.0.0.1` ou `localhost`.
*   `--port 8000` : Spécifie que l'API écoutera sur le port 8000. Vous pouvez choisir un autre port si nécessaire.
*   `--reload` : (Optionnel, recommandé pour le développement) Redémarre automatiquement le serveur lorsque des modifications sont détectées dans le code source.

Une fois le serveur lancé, vous devriez voir un message similaire à celui-ci dans votre terminal :

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using statreload
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

L'API est maintenant en cours d'exécution et prête à recevoir des requêtes.

## Accès à l'API et Documentation

FastAPI génère automatiquement une documentation interactive pour votre API, ce qui facilite la découverte et le test des endpoints. Une fois l'API lancée, vous pouvez y accéder via votre navigateur web.

### URL de Base de l'API

L'URL de base de votre API dépendra de l'hôte et du port que vous avez configurés lors du lancement. Par défaut, si vous avez utilisé `--host 0.0.0.0 --port 8000`, l'API sera accessible à l'adresse :

`http://localhost:8000`

### Documentation Interactive (Swagger UI)

FastAPI fournit une interface utilisateur Swagger (Swagger UI) qui vous permet d'explorer visuellement tous les endpoints de l'API, de comprendre leurs paramètres, d'envoyer des requêtes de test et de visualiser les réponses. Pour y accéder, ouvrez votre navigateur et naviguez vers :

`http://localhost:8000/docs`

Sur cette page, vous trouverez une liste de tous les endpoints regroupés par tags (Images, Signaux, Textes), comme défini dans le fichier `main.py`. Chaque endpoint peut être développé pour afficher sa description, ses paramètres de requête, ses modèles de données et des exemples de réponses. Vous pouvez utiliser le bouton "Try it out" pour envoyer des requêtes directement depuis l'interface.

## Module API Images

Le module `Images` gère le prétraitement et l'anonymisation des fichiers d'imagerie médicale au format DICOM. Il est accessible via le préfixe `/images`.

### Endpoint: `/images/preprocess_dicom_files/`

*   **Description** : Prétraite un ou plusieurs fichiers DICOM. Ce processus inclut l'anonymisation des données sensibles, la conversion au format NIfTI, le redimensionnement, la normalisation des pixels et l'égalisation de l'histogramme. Les résultats sont retournés sous forme d'une archive ZIP contenant les images NIfTI prétraitées, les métadonnées associées et un fichier CSV de nomenclature.
*   **Méthode HTTP** : `POST`
*   **Paramètres de Requête** :
    *   `files` (type: `List[UploadFile]`, requis) : Une liste de fichiers DICOM à télécharger pour le prétraitement.
*   **Exemple de Requête (cURL)** :

    ```bash
    curl -X POST "http://localhost:8000/images/preprocess_dicom_files/" \
      -H "accept: application/json" \
      -H "Content-Type: multipart/form-data" \
      -F "files=@/chemin/vers/votre/fichier1.dcm" \
      -F "files=@/chemin/vers/votre/fichier2.dcm"
    ```
*   vous pouvez aternativement et plus simplement utiliser la documentation(swagger ui) de Fastapi 
 
*   **Exemple de Réponse** :
    En cas de succès, l'API renvoie un fichier ZIP contenant :
    *   Un dossier `images` avec les fichiers NIfTI prétraités (ex: `processed_PAT_001_ST_001_SE_001.nii.gz`).
    *   Un dossier `metadata` avec les fichiers JSON de métadonnées pour chaque image (ex: `metadata_P001_S001_SE001.json`).
    *   Un dossier `csv_files` contenant `nomenclature_mapping.csv`, qui mappe les identifiants originaux aux identifiants anonymisés générés par l'API.

    En cas d'erreur, une réponse JSON avec un code d'état HTTP approprié et un message d'erreur sera retournée.

    ```json
    {
      "detail": "Aucun fichier n'a été téléchargé."
    }
    ```
    (Exemple de réponse d'erreur pour un fichier manquant)




## Module API Signaux

Le module `Signaux` est dédié au traitement et à l'analyse des signaux médicaux, notamment ceux au format WFDB (WaveForm DataBase). Il est accessible via le préfixe `/signaux`.

### Endpoint: `/signaux/metadata/`

*   **Description** : Récupère toutes les métadonnées disponibles pour un signal spécifique à partir de fichiers WFDB (`.hea`, `.dat`) téléchargés. Le nom du signal doit être fourni comme paramètre de requête.
*   **Méthode HTTP** : `GET`
*   **Paramètres de Requête** :
    *   `signal_name` (type: `str`, requis) : Le nom du signal (sans extension) pour lequel récupérer les métadonnées.
    *   `files` (type: `List[UploadFile]`, requis) : Une liste de fichiers WFDB (par exemple, `signal.hea` et `signal.dat`) à télécharger.
*   **Exemple de Requête (cURL)** :

    ```bash
    curl -X GET "http://localhost:8000/signaux/metadata/?signal_name=100" \
      -H "accept: application/json" \
      -H "Content-Type: multipart/form-data" \
      -F "files=@/chemin/vers/votre/100.hea" \
      -F "files=@/chemin/vers/votre/100.dat"
    ```

*   **Exemple de Réponse (Succès)** :

    ```json
    {
      "signal_name": "100",
      "metadata": {
        "record_name": "100",
        "n_sig": 2,
        "fs": 360,
        "counter_freq": null,
        "base_counter": null,
        "sig_len": 650000,
        "base_time": "10:00:00",
        "base_date": "01/01/2000",
        "comments": [
          "Age: 32",
          "Sex: M"
        ],
        "sig_name": [
          "MLII",
          "V5"
        ],
        "p_signal": null,
        "d_signal": null,
        "e_p_signal": null,
        "e_d_signal": null,
        "file_name": [
          "100.dat",
          "100.dat"
        ],
        "fmt": [
          "16",
          "16"
        ],
        "adc_gain": [
          200,
          200
        ],
        "baseline": [
          -11,
          -11
        ],
        "units": [
          "mV",
          "mV"
        ],
        "adc_res": [
          11,
          11
        ],
        "adc_zero": [
          1024,
          1024
        ],
        "init_value": [
          -11,
          4
        ],
        "checksum": [
          -27138,
          -27138
        ],
        "block_size": [
          0,
          0
        ]
      }
    }
    ```

### Endpoint: `/signaux/plot/`

*   **Description** : Génère un graphique PNG du signal spécifié à partir des fichiers WFDB téléchargés. Le graphique est retourné en tant que flux d'image.
*   **Méthode HTTP** : `GET`
*   **Paramètres de Requête** :
    *   `signal_name` (type: `str`, requis) : Le nom du signal (sans extension) pour lequel générer le graphique.
    *   `files` (type: `List[UploadFile]`, requis) : Une liste de fichiers WFDB (par exemple, `signal.hea` et `signal.dat`) à télécharger.
*   **Exemple de Requête (cURL)** :

    ```bash
    curl -X GET "http://localhost:8000/signaux/plot/?signal_name=100" \
      -H "accept: image/png" \
      -H "Content-Type: multipart/form-data" \
      -F "files=@/chemin/vers/votre/100.hea" \
      -F "files=@/chemin/vers/votre/100.dat" \
      -o "signal_plot.png"
    ```

*   **Exemple de Réponse** :
    En cas de succès, l'API renvoie directement l'image PNG du graphique. En cas d'erreur, une réponse JSON avec un message d'erreur est retournée.

### Endpoint: `/signaux/process_folder`

*   **Description** : Traite tous les signaux WFDB (`.hea`, `.dat`) téléchargés dans un dossier virtuel. Il extrait les métadonnées, génère des identifiants uniques pour chaque enregistrement et divise les informations en deux DataFrames : informations personnelles et métadonnées médicales.
*   **Méthode HTTP** : `POST`
*   **Paramètres de Requête** :
    *   `files` (type: `List[UploadFile]`, requis) : Une liste de fichiers WFDB (par exemple, `signal1.hea`, `signal1.dat`, `signal2.hea`, `signal2.dat`, etc.) à télécharger.
*   **Exemple de Requête (cURL)** :

    ```bash
    curl -X POST "http://localhost:8000/signaux/process_folder" \
      -H "accept: application/json" \
      -H "Content-Type: multipart/form-data" \
      -F "files=@/chemin/vers/votre/signal1.hea" \
      -F "files=@/chemin/vers/votre/signal1.dat" \
      -F "files=@/chemin/vers/votre/signal2.hea" \
      -F "files=@/chemin/vers/votre/signal2.dat"
    ```

*   **Exemple de Réponse (Succès)** :

    ```json
    {
      "total_signals": 2,
      "personal_info": [
        {
          "signal_name": "signal1",
          "id": "00000001"
        },
        {
          "signal_name": "signal2",
          "id": "00000002"
        }
      ],
      "medical_metadata": [
        {
          "signal_name": "signal1",
          "id": "00000001",
          "n_sig": 2,
          "fs": 360,
          "sig_len": 650000,
          "modality": "ECG"
        },
        {
          "signal_name": "signal2",
          "id": "00000002",
          "n_sig": 1,
          "fs": 250,
          "sig_len": 100000,
          "modality": "BP"
        }
      ],
      "full_metadata": [
        { ... métadonnées complètes pour signal1 ... },
        { ... métadonnées complètes pour signal2 ... }
      ]
    }
    ```

### Endpoint: `/signaux/download_metadata`

*   **Description** : Télécharge toutes les métadonnées des signaux WFDB téléchargés sous forme de fichiers CSV (informations personnelles et métadonnées médicales) compressés dans une archive ZIP.
*   **Méthode HTTP** : `POST`
*   **Paramètres de Requête** :
    *   `files` (type: `List[UploadFile]`, requis) : Une liste de fichiers WFDB à télécharger.
*   **Exemple de Requête (cURL)** :

    ```bash
    curl -X POST "http://localhost:8000/signaux/download_metadata" \
      -H "accept: application/zip" \
      -H "Content-Type: multipart/form-data" \
      -F "files=@/chemin/vers/votre/signal1.hea" \
      -F "files=@/chemin/vers/votre/signal1.dat" \
      -o "metadata_signaux_medicaux.zip"
    ```

*   **Exemple de Réponse** :
    En cas de succès, l'API renvoie directement une archive ZIP contenant `informations_personnelles.csv`, `metadonnees_medicales.csv` et un `README.md` expliquant la structure des fichiers.

### Endpoint: `/signaux/upload_signals`

*   **Description** : Permet le téléchargement de fichiers de signaux médicaux (.hea et .dat) et déclenche leur traitement pour extraire les informations personnelles et les métadonnées médicales.
*   **Méthode HTTP** : `POST`
*   **Paramètres de Requête** :
    *   `files` (type: `List[UploadFile]`, requis) : Une liste de fichiers WFDB à télécharger.
*   **Exemple de Requête (cURL)** :

    ```bash
    curl -X POST "http://localhost:8000/signaux/upload_signals" \
      -H "accept: application/json" \
      -H "Content-Type: multipart/form-data" \
      -F "files=@/chemin/vers/votre/signal1.hea" \
      -F "files=@/chemin/vers/votre/signal1.dat"
    ```

*   **Exemple de Réponse (Succès)** :

    ```json
    {
      "uploaded_files": [
        "signal1.hea",
        "signal1.dat"
      ],
      "total_signals": 1,
      "personal_info": [
        {
          "signal_name": "signal1",
          "id": "00000001"
        }
      ],
      "medical_metadata": [
        {
          "signal_name": "signal1",
          "id": "00000001",
          "n_sig": 2,
          "fs": 360,
          "sig_len": 650000,
          "modality": "ECG"
        }
      ]
    }
    ```



## Module API Texte

Le module `Text` est conçu pour l'analyse et le traitement des rapports médicaux textuels. Il permet d'extraire des informations clés, de générer des annotations et de manipuler des données textuelles. Il est accessible via le préfixe `/text`.

### Endpoint: `/text/analyser_documents`

*   **Description** : Analyse un ou plusieurs documents médicaux (DOCX ou TXT) pour en extraire des informations structurées telles que le nom, le prénom, l'âge, la date, les symptômes, les antécédents, le diagnostic et le traitement. Le texte est nettoyé et les informations sont retournées dans un format JSON.
*   **Méthode HTTP** : `POST`
*   **Paramètres de Requête** :
    *   `files` (type: `List[UploadFile]`, requis) : Une liste de fichiers DOCX ou TXT à analyser.
*   **Exemple de Requête (cURL)** :

    ```bash
    curl -X POST "http://localhost:8000/text/analyser_documents" \
      -H "accept: application/json" \
      -H "Content-Type: multipart/form-data" \
      -F "files=@/chemin/vers/votre/rapport1.docx" \
      -F "files=@/chemin/vers/votre/rapport2.txt"
    ```

*   **Exemple de Réponse (Succès)** :

    ```json
    {
      "nombre_fichiers": 2,
      "resultats": [
        {
          "filename": "rapport1.docx",
          "status": "success",
          "donnees_extraites": {
            "Nom": "Dupont",
            "Prénom": "Jean",
            "Age": 45,
            "Date": "2023-01-15",
            "Symptômes": "fievre toux fatigue",
            "Antécédents": "hypertension",
            "Diagnostic": "grippe",
            "Traitement": "repos hydratation"
          }
        },
        {
          "filename": "rapport2.txt",
          "status": "success",
          "donnees_extraites": {
            "Nom": "Martin",
            "Prénom": "Sophie",
            "Age": 30,
            "Date": "2023-02-20",
            "Symptômes": "maux tete nausees",
            "Antécédents": "aucun",
            "Diagnostic": "migraine",
            "Traitement": "analgesiques"
          }
        }
      ],
      "donnees_combinees": [
        { ... données de rapport1 ... },
        { ... données de rapport2 ... }
      ]
    }
    ```

### Endpoint: `/text/generer_annotations`

*   **Description** : Génère des annotations pour plusieurs fichiers de données médicales (DOCX, TXT, XLSX, XLS, CSV, JSON). Il extrait les informations, génère des identifiants uniques et divise les données en informations personnelles et métadonnées médicales.
*   **Méthode HTTP** : `POST`
*   **Paramètres de Requête** :
    *   `files` (type: `List[UploadFile]`, requis) : Une liste de fichiers de données médicales à traiter.
*   **Exemple de Requête (cURL)** :

    ```bash
    curl -X POST "http://localhost:8000/text/generer_annotations" \
      -H "accept: application/json" \
      -H "Content-Type: multipart/form-data" \
      -F "files=@/chemin/vers/votre/donnees.xlsx" \
      -F "files=@/chemin/vers/votre/rapport.docx"
    ```

*   **Exemple de Réponse (Succès)** :

    ```json
    {
      "nombre_fichiers": 2,
      "resultats": [
        {
          "filename": "donnees.xlsx",
          "status": "success",
          "df_personnel": [
            {
              "Nom": "Doe",
              "Prénom": "John",
              "Age": 50,
              "ID d'annotation": "230115100000001"
            }
          ],
          "df_medical": [
            {
              "Diagnostic": "Diabète",
              "Traitement": "Insuline"
            }
          ],
          "nombre_enregistrements": 1
        }
      ],
      "df_personnel_combine": [ ... ],
      "df_medical_combine": [ ... ]
    }
    ```

### Endpoint: `/text/telecharger_annotations_zip`

*   **Description** : Génère des annotations pour plusieurs fichiers de données médicales et retourne une archive ZIP contenant les informations personnelles et les métadonnées médicales au format CSV.
*   **Méthode HTTP** : `POST`
*   **Paramètres de Requête** :
    *   `files` (type: `List[UploadFile]`, requis) : Une liste de fichiers de données médicales à traiter.
*   **Exemple de Requête (cURL)** :

    ```bash
    curl -X POST "http://localhost:8000/text/telecharger_annotations_zip" \
      -H "accept: application/zip" \
      -H "Content-Type: multipart/form-data" \
      -F "files=@/chemin/vers/votre/donnees.csv" \
      -o "annotations_medicales.zip"
    ```

*   **Exemple de Réponse** :
    En cas de succès, l'API renvoie directement une archive ZIP (`annotations_medicales.zip`) contenant `df_personnel.csv` et `df_medical.csv`.

### Endpoint: `/text/supprimer_colonnes_zip`

*   **Description** : Supprime des colonnes spécifiées de plusieurs fichiers de données (XLSX, XLS, CSV, JSON) et retourne les fichiers modifiés dans une archive ZIP. La colonne 'ID d\'annotation' est protégée et ne peut pas être supprimée.
*   **Méthode HTTP** : `POST`
*   **Paramètres de Requête** :
    *   `colonnes_a_supprimer` (type: `List[str]`, requis) : Une liste des noms de colonnes à supprimer.
    *   `files` (type: `List[UploadFile]`, requis) : Une liste de fichiers de données à traiter.
*   **Exemple de Requête (cURL)** :

    ```bash
    curl -X POST "http://localhost:8000/text/supprimer_colonnes_zip" \
      -H "accept: application/zip" \
      -H "Content-Type: multipart/form-data" \
      -F "colonnes_a_supprimer=Nom" \
      -F "colonnes_a_supprimer=Prénom" \
      -F "files=@/chemin/vers/votre/patients.xlsx" \
      -o "fichiers_modifies.zip"
    ```

*   **Exemple de Réponse** :
    En cas de succès, l'API renvoie directement une archive ZIP (`fichiers_modifies.zip`) contenant les fichiers de données avec les colonnes spécifiées supprimées.

### Endpoint: `/text/sante`

*   **Description** : Endpoint de vérification de santé de l'API. Il renvoie un statut indiquant si l'API fonctionne correctement.
*   **Méthode HTTP** : `GET`
*   **Paramètres de Requête** : Aucun.
*   **Exemple de Requête (cURL)** :

    ```bash
    curl -X GET "http://localhost:8000/text/sante" \
      -H "accept: application/json"
    ```

*   **Exemple de Réponse (Succès)** :

    ```json
    {
      "statut": "OK",
      "message": "L'API fonctionne correctement",
      "timestamp": "2023-10-27T10:30:00.123456"
    }
    ```
## Test


### Utilisation de la Documentation Interactive (Swagger UI)

La méthode la plus simple pour tester l'API est d'utiliser l'interface Swagger UI, accessible à l'adresse `http://localhost:8000/docs` (ou l'adresse de votre serveur). Pour chaque endpoint, suivez ces étapes :

1.  **Sélectionnez un Endpoint** : Cliquez sur un endpoint pour le développer et afficher ses détails.
2.  **"Try it out"** : Cliquez sur le bouton "Try it out" pour activer les champs de saisie des paramètres.
3.  **Remplissez les Paramètres** : Entrez les valeurs requises pour les paramètres de l'endpoint. Pour les endpoints qui acceptent des fichiers (`UploadFile`), vous pourrez utiliser un sélecteur de fichiers pour télécharger les fichiers nécessaires.
4.  **Exécutez la Requête** : Cliquez sur le bouton "Execute" pour envoyer la requête à l'API.
5.  **Analysez la Réponse** : La réponse de l'API, y compris le code de statut HTTP, les en-têtes et le corps de la réponse, sera affichée directement dans l'interface. Cela vous permet de vérifier si l'API retourne les données attendues et gère correctement les erreurs.

### Test avec Python (bibliothèque `requests`)

Pour des tests plus complexes ou pour intégrer l'API dans une application Python, la bibliothèque `requests` est un excellent choix.

**Exemple (POST avec fichier) :**

```python
import requests

url = "http://localhost:8000/text/analyser_documents"
files = {
    "files": ("rapport.docx", open("/chemin/vers/votre/rapport.docx", "rb"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
}

response = requests.post(url, files=files)

if response.status_code == 200:
    print("Succès:")
    print(response.json())
else:
    print(f"Erreur: {response.status_code}")
    print(response.text)
```

Cet exemple montre comment envoyer un fichier DOCX à l'endpoint `/text/analyser_documents` et afficher la réponse. Adaptez l'URL, le nom du fichier et le type MIME (`application/vnd.openxmlformats-officedocument.wordprocessingml.document` pour DOCX, `text/plain` pour TXT, etc.) selon l'endpoint que vous testez.

### Gestion des Erreurs

L'API est conçue pour renvoyer des codes de statut HTTP standard en cas d'erreur, accompagnés de messages JSON explicatifs. Par exemple :

*   `400 Bad Request` : Si les paramètres de la requête sont invalides ou manquants.
*   `404 Not Found` : Si une ressource demandée n'existe pas.
*   `422 Unprocessable Entity` : Si les données fournies ne peuvent pas être traitées (par exemple, un fichier DICOM invalide).
*   `500 Internal Server Error` : Pour les erreurs inattendues côté serveur.

## Conclusion

Cette documentation a couvert les aspects essentiels de l'API Médicale, depuis sa mise en place jusqu'à l'utilisation détaillée de ses endpoints pour le traitement des images, signaux et textes médicaux.

L'API Médicale Unifiée est un outil puissant, offrant des capacités d'anonymisation, de prétraitement et d'extraction d'informations cruciales. Nous espérons que cette documentation vous sera utile et facilitera votre travail avec cette API.
