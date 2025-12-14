# API Médicale Unifiée - Documentation Complète

## 📋 Table des matières

1. [Introduction](#introduction)
2. [Installation et Configuration](#installation-et-configuration)
3. [Démarrage Rapide](#démarrage-rapide)
4. [Architecture et Fonctionnalités](#architecture-et-fonctionnalités)
5. [Endpoints Système](#endpoints-système)
6. [Module Images DICOM](#module-images-dicom)
7. [Module Signaux Médicaux](#module-signaux-médicaux)
8. [Module Textes Médicaux](#module-textes-médicaux)
9. [Module Traitement par Lots](#module-traitement-par-lots)
10. [Système de Suivi des Jobs](#système-de-suivi-des-jobs)
11. [Sécurité et Limitations](#sécurité-et-limitations)
12. [Codes d'Erreur](#codes-derreur)
13. [Exemples d'Utilisation](#exemples-dutilisation)

---

## Introduction

L'API Médicale Unifiée v2.0 est une interface REST développée avec FastAPI pour le traitement et l'analyse de données médicales. Elle supporte trois types principaux de données :

- **Images médicales** : Fichiers DICOM (CT, IRM, radiographies)
- **Signaux physiologiques** : Format WFDB (ECG, EEG)
- **Documents textuels** : Rapports médicaux (DOCX, TXT, CSV, Excel, JSON)

### 🎯 Fonctionnalités principales

- ✅ **Anonymisation** : Protection des données sensibles des patients
- ✅ **Prétraitement** : Redimensionnement, normalisation, amélioration d'images
- ✅ **Extraction de métadonnées** : Récupération complète des informations médicales
- ✅ **Annotations automatiques** : Génération d'identifiants uniques et structuration
- ✅ **Traitement asynchrone** : Suivi en temps réel avec système de jobs
- ✅ **Rate limiting** : Protection contre les abus (100 req/min)
- ✅ **Logging complet** : Traçabilité de toutes les requêtes
- ✅ **Versioning API** : Support des versions futures (/api/v1/)

### 🔧 Technologies utilisées

- **Framework** : FastAPI 0.116+
- **Serveur** : Uvicorn (ASGI)
- **Traitement d'images** : pydicom, nibabel, scikit-image, Pillow
- **Signaux** : WFDB
- **Documents** : python-docx, pandas, NLTK
- **Format de sortie** : ZIP, JSON, CSV, Excel

---

## Installation et Configuration

### Prérequis

- Python 3.8 ou supérieur
- pip (gestionnaire de paquets Python)
- Environnement virtuel (recommandé)

### Installation

1. **Cloner ou télécharger le projet** :
```bash
cd /chemin/vers/api
```

2. **Activer l'environnement virtuel** :
```bash
source .venv/bin/activate  # Linux/Mac
# ou
.venv\\Scripts\\activate  # Windows
```

3. **Installer les dépendances** :
```bash
pip install -r requirements.txt
```

4. **Configurer l'environnement** :
```bash
cp .env.example .env
```

Éditez le fichier `.env` :
```bash
# CORS - origines autorisées (séparées par des virgules)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# URL de base pour les appels API internes
API_BASE_URL=http://localhost:8000

# Limitation de débit
RATE_LIMIT_CALLS=100        # Nombre de requêtes autorisées
RATE_LIMIT_PERIOD=60        # Période en secondes
```

### Structure du projet

```
api/
├── app/
│   ├── __init__.py
│   ├── main.py              # Point d'entrée principal
│   ├── dependencies.py      # Fonctions de validation et traitement
│   ├── middleware.py        # Middlewares (rate limiting, logging)
│   ├── job_tracker.py       # Système de suivi des jobs
│   └── routers/
│       ├── __init__.py
│       ├── api_images.py    # Endpoints images DICOM
│       ├── api_signaux.py   # Endpoints signaux médicaux
│       ├── api_text.py      # Endpoints textes médicaux
│       └── api_batch.py     # Endpoints traitement par lots
├── .env                     # Configuration (ne pas versionner)
├── .env.example             # Exemple de configuration
├── requirements.txt         # Dépendances Python
├── JOB_TRACKING.md          # Documentation système de jobs
└── Readme.md                # Ce fichier
```

---

## Démarrage Rapide

### Lancer le serveur

**Mode développement** (avec rechargement automatique) :
```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Mode production** :
```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Le serveur démarre sur `http://localhost:8000`

### Vérifier le fonctionnement

```bash
# Test du endpoint de santé
curl http://localhost:8000/health

# Réponse attendue :
# {"status":"healthy","service":"API Médicale Unifiée","version":"2.0.0"}
```

### Accéder à la documentation interactive

- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc

---

## Architecture et Fonctionnalités

### Versioning de l'API

Tous les endpoints sont disponibles sous deux chemins :

**✅ Recommandé** - Endpoints versionnés :
```
/api/v1/images/...
/api/v1/signaux/...
/api/v1/text/...
/api/v1/batch/...
```

**⚠️ Legacy** - Rétrocompatibilité (sera déprécié) :
```
/images/...
/signaux/...
/text/...
/batch/...
```

### Middlewares actifs

L'API utilise plusieurs middlewares dans l'ordre suivant :

1. **InputSanitizationMiddleware** : Détection de patterns malveillants
2. **RateLimitMiddleware** : Limitation du nombre de requêtes
3. **RequestLoggingMiddleware** : Journalisation de toutes les requêtes
4. **CORSMiddleware** : Gestion des origines autorisées

### Format des réponses

**Succès** :
```json
{
  "data": { ... },
  "metadata": { ... }
}
```

**Erreur** :
```json
{
  "detail": "Message d'erreur générique",
  "error_type": "type_erreur"
}
```

### En-têtes de réponse

Toutes les réponses incluent ces en-têtes :

```
X-Request-ID: uuid-unique          # ID de traçage de la requête
X-RateLimit-Limit: 100              # Limite de requêtes
X-RateLimit-Remaining: 95           # Requêtes restantes
X-RateLimit-Reset: 1765734553       # Timestamp de réinitialisation
```

---

## Endpoints Système

### GET /

**Description** : Informations générales sur l'API

**Réponse** :
```json
{
  "message": "API Médicale Unifiée",
  "version": "2.0.0",
  "docs": "/docs",
  "health": "/health",
  "jobs": "/jobs",
  "api_versions": {
    "v1": "/api/v1"
  }
}
```

### GET /health

**Description** : Vérification de l'état de santé de l'API (exclu du rate limiting)

**Réponse** :
```json
{
  "status": "healthy",
  "service": "API Médicale Unifiée",
  "version": "2.0.0"
}
```

**Codes de statut** :
- `200 OK` : API fonctionnelle

### GET /jobs

**Description** : Liste les jobs récents avec possibilité de filtrage

**Paramètres de requête** :
- `status` (optionnel) : Filtrer par statut (`pending`, `processing`, `completed`, `failed`, `cancelled`)
- `limit` (optionnel) : Nombre maximum de résultats (défaut: 50, max: 100)

**Exemple** :
```bash
GET /jobs?status=processing&limit=20
```

**Réponse** :
```json
{
  "total": 2,
  "jobs": [
    {
      "job_id": "abc-123",
      "status": "processing",
      "progress_percent": 45,
      "message": "Traitement du fichier 3/10",
      "created_at": "2025-12-14T18:00:00.123Z",
      "started_at": "2025-12-14T18:00:01.456Z",
      "completed_at": null,
      "result": null,
      "error": null,
      "metadata": {
        "operation": "preprocess_dicom",
        "file_count": 10
      }
    }
  ]
}
```

### GET /jobs/{job_id}

**Description** : Obtenir le statut détaillé d'un job spécifique

**Paramètres** :
- `job_id` (path, requis) : Identifiant unique du job

**Exemple** :
```bash
GET /jobs/abc-123-def-456
```

**Réponse** (en cours) :
```json
{
  "job_id": "abc-123-def-456",
  "status": "processing",
  "progress_percent": 65,
  "message": "Création de l'archive ZIP...",
  "created_at": "2025-12-14T18:00:00.123Z",
  "started_at": "2025-12-14T18:00:01.456Z",
  "completed_at": null,
  "result": null,
  "error": null,
  "metadata": {
    "operation": "preprocess_dicom",
    "file_count": 5,
    "dimensions": {"height": 256, "width": 256}
  }
}
```

**Réponse** (terminé) :
```json
{
  "job_id": "abc-123-def-456",
  "status": "completed",
  "progress_percent": 100,
  "message": "Traitement terminé avec succès!",
  "created_at": "2025-12-14T18:00:00.123Z",
  "started_at": "2025-12-14T18:00:01.456Z",
  "completed_at": "2025-12-14T18:02:30.789Z",
  "result": {
    "files_processed": 5
  },
  "error": null
}
```

**Codes de statut** :
- `200 OK` : Job trouvé
- `404 Not Found` : Job inexistant ou expiré

### DELETE /jobs/{job_id}

**Description** : Annuler ou supprimer un job

**Paramètres** :
- `job_id` (path, requis) : Identifiant du job

**Réponse** :
```json
{
  "message": "Job annulé",
  "job_id": "abc-123-def-456"
}
```

**Codes de statut** :
- `200 OK` : Job annulé
- `404 Not Found` : Job introuvable

---

## Module Images DICOM

Ce module gère le traitement des fichiers d'imagerie médicale au format DICOM.

### POST /api/v1/images/preprocess_dicom_files/

**Description** : Prétraitement synchrone de fichiers DICOM (bloquant, peut être long)

**Paramètres** :
- `files` (form-data, requis) : Liste de fichiers DICOM
- `n` (query, optionnel) : Hauteur de l'image de sortie (défaut: 256)
- `m` (query, optionnel) : Largeur de l'image de sortie (défaut: 256)

**Extensions acceptées** : `.dcm`, `.dicom`

**Limites** :
- Taille maximale par fichier : 100 MB
- Nombre maximum de fichiers : 50

**Traitement effectué** :
1. Validation des fichiers
2. Anonymisation des données sensibles (nom, ID patient, dates, etc.)
3. Conversion DICOM → NIfTI
4. Redimensionnement aux dimensions spécifiées
5. Normalisation des valeurs de pixels (0-1)
6. Égalisation d'histogramme pour amélioration du contraste
7. Génération de métadonnées (JSON + HDR)
8. Création d'un fichier CSV de nomenclature

**Exemple de requête** :
```bash
curl -X POST "http://localhost:8000/api/v1/images/preprocess_dicom_files/?n=512&m=512" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@scan1.dcm" \
  -F "files=@scan2.dcm" \
  -o resultat.zip
```

**Réponse** : Fichier ZIP contenant :
```
processed_data/
├── images/
│   ├── processed_PAT_001_ST_001_SE_001.nii.gz
│   └── processed_PAT_002_ST_002_SE_002.nii.gz
├── metadata/
│   ├── metadata_P001_S001_SE001.json
│   └── metadata_P002_S002_SE002.json
├── metadata_hdr/
│   ├── metadata_P001_S001_SE001.hdr
│   └── metadata_P002_S002_SE002.hdr
└── csv_files/
    └── nomenclature_mapping.csv
```

**Structure du CSV de nomenclature** :
```csv
patient_id_nomenclature,study_id_nomenclature,series_id_nomenclature,original_patient_id,original_study_id,original_modality,original_study_date,Study_Description,Study_Time
P001,S001,SE001,PATIENT123,STUDY456,CT,20251214,Brain Scan,143000
```

**Codes de statut** :
- `200 OK` : Traitement réussi, retourne le ZIP
- `400 Bad Request` : Fichiers invalides, extension non autorisée, ou fichier vide
- `500 Internal Server Error` : Erreur de traitement

### POST /api/v1/images/preprocess_dicom_files_async/

**Description** : Version asynchrone - retourne immédiatement un job_id pour suivi en temps réel

**Paramètres** : Identiques à la version synchrone

**Exemple de requête** :
```bash
curl -X POST "http://localhost:8000/api/v1/images/preprocess_dicom_files_async/" \
  -F "files=@scan.dcm" \
  -F "n=512" \
  -F "m=512"
```

**Réponse immédiate** :
```json
{
  "job_id": "abc-123-def-456",
  "status": "pending",
  "message": "Traitement lancé. Utilisez GET /jobs/{job_id} pour vérifier le statut.",
  "status_url": "/jobs/abc-123-def-456"
}
```

**Workflow** :
1. Soumettre les fichiers → Recevoir `job_id`
2. Interroger `GET /jobs/{job_id}` régulièrement (toutes les 2-5 secondes)
3. Quand `status == "completed"`, télécharger via `/api/v1/images/download_result/{job_id}`

**Étapes de progression** :
- 5% : Initialisation
- 10-80% : Traitement des fichiers (progressif)
- 85% : Création du CSV de nomenclature
- 95% : Création de l'archive ZIP
- 100% : Terminé

### GET /api/v1/images/download_result/{job_id}

**Description** : Télécharger le résultat d'un job terminé

**Paramètres** :
- `job_id` (path, requis) : Identifiant du job

**Exemple** :
```bash
curl "http://localhost:8000/api/v1/images/download_result/abc-123" -o resultat.zip
```

**Réponse** : Fichier ZIP (identique à la version synchrone)

**Codes de statut** :
- `200 OK` : Fichier ZIP retourné
- `400 Bad Request` : Job non terminé
- `404 Not Found` : Job introuvable ou fichier expiré

### POST /api/v1/images/convert_dicom_for_viewer

**Description** : Convertir un fichier DICOM en format visualisable (JSON avec image base64)

**Paramètres** :
- `file` (form-data, requis) : Un seul fichier DICOM

**Exemple** :
```bash
curl -X POST "http://localhost:8000/api/v1/images/convert_dicom_for_viewer" \
  -F "file=@scan.dcm"
```

**Réponse** :
```json
{
  "success": true,
  "image_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...",
  "metadata": {
    "patient_name": "Anonymized",
    "patient_id": "Unknown",
    "patient_birth_date": "Unknown",
    "patient_sex": "M",
    "modality": "CT",
    "body_part": "BRAIN",
    "study_date": "20251214",
    "study_time": "143000",
    "study_description": "Brain CT",
    "series_description": "Axial",
    "institution": "Hospital ABC",
    "manufacturer": "GE Healthcare",
    "rows": 512,
    "columns": 512,
    "pixel_spacing": "[0.5, 0.5]",
    "slice_thickness": "5.0"
  },
  "original_filename": "scan.dcm"
}
```

**Codes de statut** :
- `200 OK` : Conversion réussie
- `500 Internal Server Error` : Erreur de conversion

---

## Module Signaux Médicaux

Ce module traite les fichiers de signaux physiologiques au format WFDB (ECG, EEG, etc.).

### POST /api/v1/signaux/metadata/

**Description** : Récupérer les métadonnées d'un signal spécifique

**Paramètres** :
- `signal_name` (form-data, requis) : Nom du signal (sans extension)
- `files` (form-data, requis) : Fichiers du signal (.hea et .dat)

**Extensions acceptées** : `.hea`, `.dat`

**Exemple** :
```bash
curl -X POST "http://localhost:8000/api/v1/signaux/metadata/" \
  -F "signal_name=100" \
  -F "files=@100.hea" \
  -F "files=@100.dat"
```

**Réponse** :
```json
{
  "signal_name": "100",
  "metadata": {
    "record_name": "100",
    "n_sig": 2,
    "fs": 360.0,
    "sig_len": 650000,
    "base_time": "00:00:00",
    "base_date": "01/01/2000",
    "sig_name": ["MLII", "V5"],
    "units": ["mV", "mV"],
    "comments": ["Age: 69", "Sex: M"]
  }
}
```

**Codes de statut** :
- `200 OK` : Métadonnées récupérées
- `400 Bad Request` : Fichiers invalides
- `500 Internal Server Error` : Erreur de lecture

### POST /api/v1/signaux/plot/

**Description** : Générer un graphique du signal

**Paramètres** :
- `signal_name` (form-data, requis) : Nom du signal
- `files` (form-data, requis) : Fichiers du signal

**Exemple** :
```bash
curl -X POST "http://localhost:8000/api/v1/signaux/plot/" \
  -F "signal_name=100" \
  -F "files=@100.hea" \
  -F "files=@100.dat" \
  -o signal_plot.png
```

**Réponse** : Image PNG du graphique du signal

**Codes de statut** :
- `200 OK` : Image PNG retournée
- `500 Internal Server Error` : Erreur de génération

### POST /api/v1/signaux/process_folder

**Description** : Traiter plusieurs signaux et retourner leurs métadonnées

**Paramètres** :
- `files` (form-data, requis) : Tous les fichiers de signaux (.hea et .dat)

**Exemple** :
```bash
curl -X POST "http://localhost:8000/api/v1/signaux/process_folder" \
  -F "files=@100.hea" \
  -F "files=@100.dat" \
  -F "files=@101.hea" \
  -F "files=@101.dat"
```

**Réponse** :
```json
{
  "total_signals": 2,
  "personal_info": [
    {
      "signal_name": "100",
      "id": "00000001",
      "nom": "Unknown",
      "prenom": "Unknown",
      "age": 0
    }
  ],
  "medical_metadata": [
    {
      "signal_name": "100",
      "id": "00000001",
      "n_sig": 2,
      "fs": 360.0,
      "sig_len": 650000
    }
  ],
  "full_metadata": [ /* Toutes les métadonnées combinées */ ]
}
```

### POST /api/v1/signaux/download_metadata

**Description** : Télécharger les métadonnées de plusieurs signaux en ZIP

**Paramètres** :
- `files` (form-data, requis) : Fichiers de signaux

**Réponse** : Fichier ZIP contenant :
```
metadata_signaux_medicaux.zip
├── informations_personnelles.csv
├── metadonnees_medicales.csv
└── README.md
```

**Codes de statut** :
- `200 OK` : ZIP retourné
- `500 Internal Server Error` : Erreur de traitement

### POST /api/v1/signaux/convert_signal_for_viewer

**Description** : Convertir un signal pour visualisation (format JSON)

**Paramètres** :
- `files` (form-data, requis) : Fichiers du signal (.hea et .dat)

**Réponse** :
```json
{
  "success": true,
  "signal_data": [
    [0, 0.123],
    [1, 0.145],
    [2, 0.132]
    /* ... jusqu'à 5000 points max */
  ],
  "metadata": {
    "record_name": "100",
    "sampling_frequency": 360.0,
    "duration": 1805.56,
    "n_signals": 2,
    "signal_names": ["MLII", "V5"],
    "units": ["mV", "mV"],
    "comments": ["Age: 69", "Sex: M"]
  },
  "original_filenames": ["100.hea", "100.dat"]
}
```

---

## Module Textes Médicaux

Ce module analyse et annote des rapports médicaux textuels.

### POST /api/v1/text/analyser_documents

**Description** : Analyser plusieurs documents médicaux et extraire les informations

**Paramètres** :
- `files` (form-data, requis) : Documents médicaux

**Extensions acceptées** : `.docx`, `.txt`, `.xlsx`, `.xls`, `.csv`, `.json`

**Exemple** :
```bash
curl -X POST "http://localhost:8000/api/v1/text/analyser_documents" \
  -F "files=@rapport1.docx" \
  -F "files=@rapport2.txt"
```

**Format de document attendu** :
```
Patient: Dupont Jean, 45 ans
Date: 14 décembre 2025

Motif de consultation: Douleurs thoraciques
Antécédents médicaux: Hypertension
Diagnostic: Angine de poitrine
Traitement: Nitroglycérine, repos
```

ou

```
Nom: Dupont
Prénom: Jean
Âge: 45
Date: 14/12/2025
Motif de consultation: Douleurs thoraciques
Antécédents médicaux: Hypertension
Diagnostic: Angine de poitrine
Traitement: Nitroglycérine
```

**Réponse** :
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
        "Date": "14 décembre 2025",
        "Symptômes": "douleurs thoraciques",
        "Antécédents": "hypertension",
        "Diagnostic": "angine poitrine",
        "Traitement": "nitroglycérine repos",
        "Fichier_source": "rapport1.docx"
      }
    }
  ],
  "donnees_combinees": [
    { /* Toutes les données extraites combinées */ }
  ]
}
```

**Nettoyage automatique** :
- Conversion en minuscules
- Suppression des stopwords français et médicaux
- Suppression des chiffres et ponctuation
- Filtrage des mots courts (<3 caractères)

### POST /api/v1/text/generer_annotations

**Description** : Générer des annotations pour des fichiers de données médicales

**Paramètres** :
- `files` (form-data, requis) : Fichiers de données

**Réponse** :
```json
{
  "nombre_fichiers": 1,
  "resultats": [
    {
      "filename": "donnees.csv",
      "status": "success",
      "df_personnel": [
        {
          "Nom": "Dupont",
          "Prénom": "Jean",
          "Année de naissance": 1980,
          "ID d'annotation": 25121404500
        }
      ],
      "df_medical": [
        {
          "ID d'annotation": 25121404500,
          "Date": "14 décembre 2025",
          "Symptômes": "douleurs thoraciques",
          "Diagnostic": "angine poitrine"
        }
      ],
      "nombre_enregistrements": 1
    }
  ],
  "df_personnel_combine": [ /* Données personnelles combinées */ ],
  "df_medical_combine": [ /* Données médicales combinées */ ]
}
```

**Format ID d'annotation** (11 chiffres) :
```
AA MM JJ S AAA D
└┬┘└┬┘└┬┘│ └┬┘ │
 │  │  │ │  │  └─ Diagnostic (0=normal, 1=anormal)
 │  │  │ │  └──── Âge sur 3 chiffres
 │  │  │ └─────── Sexe (0=homme, 1=femme)
 │  │  └───────── Jour
 │  └──────────── Mois
 └─────────────── Année (2 derniers chiffres)
```

### POST /api/v1/text/telecharger_annotations_zip

**Description** : Générer des annotations et télécharger en ZIP

**Paramètres** :
- `files` (form-data, requis) : Fichiers à annoter

**Réponse** : Fichier ZIP contenant :
```
annotations_medicales.zip
├── donnees_personnelles.csv
├── donnees_personnelles.xlsx
├── donnees_personnelles.json
├── donnees_medicales.csv
├── donnees_medicales.xlsx
├── donnees_medicales.json
└── README.md
```

### POST /api/v1/text/supprimer_colonnes_zip

**Description** : Supprimer des colonnes de plusieurs fichiers

**Paramètres** :
- `colonnes_a_supprimer` (form-data, requis) : Liste de noms de colonnes (répété)
- `files` (form-data, requis) : Fichiers à modifier

**Exemple** :
```bash
curl -X POST "http://localhost:8000/api/v1/text/supprimer_colonnes_zip" \
  -F "colonnes_a_supprimer=Age" \
  -F "colonnes_a_supprimer=Date" \
  -F "files=@donnees.csv"
```

**Réponse** : ZIP avec fichiers modifiés

**Note** : La colonne "ID d'annotation" est protégée et ne peut pas être supprimée

---

## Module Traitement par Lots

Ce module traite des archives ZIP contenant plusieurs types de fichiers médicaux.

### POST /api/v1/batch/process_zip

**Description** : Traiter une archive ZIP mixte contenant images, signaux et textes

**Paramètres** :
- `file` (form-data, requis) : Fichier ZIP

**Limites de sécurité** :
- Taille max décompressée : 500 MB
- Nombre max de fichiers : 1000
- Ratio de compression max : 100 (protection ZIP bomb)

**Structure ZIP attendue** :
```
archive.zip
├── images/
│   ├── scan1.dcm
│   └── scan2.dcm
├── signaux/
│   ├── ecg1.hea
│   ├── ecg1.dat
│   ├── ecg2.hea
│   └── ecg2.dat
└── rapports/
    ├── rapport1.docx
    └── rapport2.txt
```

**Traitement effectué** :
1. Extraction sécurisée du ZIP
2. Catégorisation automatique des fichiers par type
3. Traitement parallèle de chaque catégorie via les endpoints correspondants
4. Création d'une archive ZIP de résultats avec rapport

**Exemple** :
```bash
curl -X POST "http://localhost:8000/api/v1/batch/process_zip" \
  -F "file=@donnees_medicales.zip" \
  -o resultats.zip
```

**Réponse** : ZIP contenant :
```
processed_batch_20251214_180000.zip
├── images_results.zip        # Résultats du traitement DICOM
├── signals_results.zip        # Résultats du traitement signaux
├── text_results.zip           # Résultats du traitement textes
└── processing_report.txt      # Rapport détaillé
```

**Exemple de rapport** :
```
============================================================
RAPPORT DE TRAITEMENT PAR LOTS
============================================================

Fichier source: donnees_medicales.zip
Date de traitement: 2025-12-14 18:00:00

Fichiers extraits: 15

--- CATÉGORISATION ---
Images DICOM: 5 fichiers
Signaux: 2 groupes
Documents texte: 3 fichiers
Non reconnus: 0 fichiers

--- RÉSULTATS ---
✓ images: Traité avec succès
✓ signals: Traité avec succès
✓ text: Traité avec succès

============================================================
Traitement terminé.
============================================================
```

**Codes de statut** :
- `200 OK` : Traitement réussi
- `400 Bad Request` : ZIP invalide, trop volumineux, ou suspect
- `500 Internal Server Error` : Erreur de traitement

### GET /api/v1/batch/

**Description** : Informations sur le module batch

**Réponse** :
```json
{
  "message": "Batch Processing API",
  "version": "1.0.0",
  "endpoint": "/batch/process_zip",
  "description": "Process ZIP files containing mixed medical data types",
  "supported_types": {
    "images": [".dcm", ".dicom"],
    "signals": [".hea", ".dat"],
    "text": [".docx", ".txt", ".xlsx", ".xls", ".csv", ".json"]
  },
  "limits": {
    "max_files": 1000,
    "max_size_mb": 500,
    "max_compression_ratio": 100
  }
}
```

---

## Système de Suivi des Jobs

Le système de jobs permet le suivi en temps réel des opérations longues.

### Workflow typique

```
1. Soumettre un job
   POST /api/v1/images/preprocess_dicom_files_async/
   → Retourne: {"job_id": "abc-123", "status": "pending"}

2. Interroger le statut (polling toutes les 2-5 secondes)
   GET /jobs/abc-123
   → {"status": "processing", "progress_percent": 45, "message": "..."}

3. Attendre la complétion
   GET /jobs/abc-123
   → {"status": "completed", "progress_percent": 100}

4. Télécharger le résultat
   GET /api/v1/images/download_result/abc-123
   → Fichier ZIP
```

### États des jobs

| État | Description | Actions possibles |
|------|-------------|-------------------|
| `pending` | En attente de traitement | Annuler |
| `processing` | En cours de traitement | Annuler |
| `completed` | Terminé avec succès | Télécharger, Supprimer |
| `failed` | Échec du traitement | Consulter erreur, Supprimer |
| `cancelled` | Annulé par l'utilisateur | Supprimer |

### Progression du traitement DICOM

- **0-5%** : Initialisation
- **10-80%** : Traitement des fichiers individuels
- **85%** : Création CSV de nomenclature
- **95%** : Création archive ZIP
- **100%** : Terminé

### Stockage et persistence

**⚠️ Important** :
- Stockage en mémoire (jobs perdus au redémarrage)
- Limite de 1000 jobs en mémoire
- Nettoyage automatique des anciens jobs
- Pour la production : utiliser Redis ou base de données

### Exemple complet Python

```python
import requests
import time

# 1. Soumettre le job
files = {'files': open('scan.dcm', 'rb')}
response = requests.post(
    'http://localhost:8000/api/v1/images/preprocess_dicom_files_async/',
    files=files
)
job_id = response.json()['job_id']
print(f"Job créé: {job_id}")

# 2. Suivre la progression
while True:
    status_response = requests.get(f'http://localhost:8000/jobs/{job_id}')
    status = status_response.json()
    
    print(f"[{status['progress_percent']}%] {status['message']}")
    
    if status['status'] in ['completed', 'failed', 'cancelled']:
        break
    
    time.sleep(2)  # Attendre 2 secondes avant la prochaine vérification

# 3. Télécharger si succès
if status['status'] == 'completed':
    result = requests.get(
        f'http://localhost:8000/api/v1/images/download_result/{job_id}',
        stream=True
    )
    with open('resultat.zip', 'wb') as f:
        f.write(result.content)
    print("✓ Résultat téléchargé!")
else:
    print(f"✗ Échec: {status.get('error', 'Erreur inconnue')}")
```

---

## Sécurité et Limitations

### Rate Limiting

**Configuration par défaut** :
- 100 requêtes par période de 60 secondes par adresse IP
- Exclusions : `/health`, `/docs`, `/redoc`, `/openapi.json`

**En-têtes de réponse** :
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1765734553
```

**Réponse si limite dépassée** (HTTP 429) :
```json
{
  "detail": "Trop de requêtes. Veuillez réessayer plus tard.",
  "error_type": "rate_limit_exceeded"
}
```

**Configuration** :
```bash
# Dans .env
RATE_LIMIT_CALLS=200
RATE_LIMIT_PERIOD=60
```

### Validation des entrées

**Fichiers** :
- ✅ Vérification des extensions autorisées
- ✅ Limite de taille (100 MB par fichier)
- ✅ Limite du nombre de fichiers (50 par requête)
- ✅ Détection de fichiers vides
- ✅ Protection contre traversée de chemin (`../`)
- ✅ Sanitisation des noms de fichiers

**Paramètres** :
- ✅ Détection de patterns malveillants (`<script>`, `javascript:`, etc.)
- ✅ Protection XSS et injection
- ✅ Blocage automatique des requêtes suspectes

**Exemple de requête bloquée** :
```bash
curl "http://localhost:8000/api/v1/signaux/?test=../etc/passwd"
# Réponse: {"detail":"Requête invalide détectée.","error_type":"invalid_input"}
```

### Gestion des erreurs

**Principe** : Ne jamais exposer les détails internes

**Erreur serveur** :
```json
{
  "detail": "Une erreur interne s'est produite. Veuillez réessayer plus tard.",
  "error_type": "internal_error"
}
```

**Journalisation** :
- Détails complets côté serveur
- ID de requête unique pour traçage
- Stack traces dans les logs

### Logging

Chaque requête génère :
```
INFO:app.middleware:Request started | ID: abc-123 | Method: POST | Path: /api/v1/images/... | Client: 127.0.0.1
INFO:app.middleware:Request completed | ID: abc-123 | Status: 200 | Duration: 2.345s
```

En cas d'erreur :
```
ERROR:app.middleware:Request failed | ID: abc-123 | Error: ... | Duration: 0.123s
```

### CORS

**Configuration** :
```bash
# Dans .env
ALLOWED_ORIGINS=http://localhost:3000,https://app.example.com
```

**⚠️ Ne jamais utiliser `*` en production !**

### Limites techniques

| Ressource | Limite | Configuration |
|-----------|--------|---------------|
| Taille fichier | 100 MB | `MAX_FILE_SIZE` |
| Nombre fichiers | 50 | `MAX_FILES` |
| Taille ZIP | 500 MB | `MAX_EXTRACTION_SIZE` |
| Fichiers ZIP | 1000 | `MAX_FILES_IN_ZIP` |
| Ratio compression | 100 | `MAX_COMPRESSION_RATIO` |
| Jobs en mémoire | 1000 | `JobTracker(max_jobs)` |

---

## Codes d'Erreur

### HTTP 400 - Bad Request

**Causes** :
- Fichier manquant ou invalide
- Extension non autorisée
- Fichier vide
- Fichier trop volumineux
- Trop de fichiers
- Nom de fichier suspect
- Paramètre invalide
- Job non terminé (lors du téléchargement)

**Exemples** :
```json
{"detail": "Aucun fichier n'a été téléchargé."}
{"detail": "Extension de fichier non autorisée : '.exe'"}
{"detail": "Fichier 'scan.dcm' trop volumineux. Taille maximale : 100.0MB"}
{"detail": "Trop de fichiers. Maximum autorisé : 50, reçu : 75"}
{"detail": "Requête invalide détectée."}
```

### HTTP 404 - Not Found

**Causes** :
- Job inexistant ou expiré
- Résultat non disponible
- Fichier résultat supprimé

**Exemples** :
```json
{"detail": "Job non trouvé. Il a peut-être expiré ou n'existe pas."}
{"detail": "Le fichier résultat n'est plus disponible."}
```

### HTTP 429 - Too Many Requests

**Cause** : Rate limit dépassé

**Réponse** :
```json
{
  "detail": "Trop de requêtes. Veuillez réessayer plus tard.",
  "error_type": "rate_limit_exceeded"
}
```

**En-têtes** :
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1765734613
```

### HTTP 500 - Internal Server Error

**Causes** :
- Erreur de traitement
- Erreur de conversion
- Erreur d'écriture fichier
- Erreur système

**Réponse** :
```json
{
  "detail": "Une erreur interne s'est produite. Veuillez réessayer plus tard.",
  "error_type": "internal_error"
}
```

**Note** : Les détails complets sont dans les logs serveur avec l'ID de requête

---

## Exemples d'Utilisation

### Exemple 1 : Traitement DICOM synchrone

```bash
# Prétraiter 3 fichiers DICOM en 512x512
curl -X POST "http://localhost:8000/api/v1/images/preprocess_dicom_files/?n=512&m=512" \
  -F "files=@scan1.dcm" \
  -F "files=@scan2.dcm" \
  -F "files=@scan3.dcm" \
  -o resultats_dicom.zip

# Extraire et visualiser
unzip resultats_dicom.zip
cd processed_data
ls -R
```

### Exemple 2 : Traitement DICOM asynchrone avec suivi

```python
import requests
import time
import sys

API_URL = "http://localhost:8000"

# Soumettre le job
files = [
    ('files', open('scan1.dcm', 'rb')),
    ('files', open('scan2.dcm', 'rb'))
]
response = requests.post(
    f"{API_URL}/api/v1/images/preprocess_dicom_files_async/",
    files=files,
    params={'n': 512, 'm': 512}
)
job_id = response.json()['job_id']
print(f"Job ID: {job_id}")

# Suivre la progression
while True:
    status = requests.get(f"{API_URL}/jobs/{job_id}").json()
    
    # Afficher la barre de progression
    percent = status['progress_percent']
    bar_length = 50
    filled = int(bar_length * percent / 100)
    bar = '█' * filled + '░' * (bar_length - filled)
    
    sys.stdout.write(f"\r[{bar}] {percent}% - {status['message']}")
    sys.stdout.flush()
    
    if status['status'] in ['completed', 'failed', 'cancelled']:
        print()
        break
    
    time.sleep(2)

# Télécharger si succès
if status['status'] == 'completed':
    result = requests.get(f"{API_URL}/api/v1/images/download_result/{job_id}")
    with open('resultat.zip', 'wb') as f:
        f.write(result.content)
    print("✓ Résultat téléchargé dans resultat.zip")
```

### Exemple 3 : Analyse de signaux

```bash
# Récupérer les métadonnées d'un ECG
curl -X POST "http://localhost:8000/api/v1/signaux/metadata/" \
  -F "signal_name=100" \
  -F "files=@100.hea" \
  -F "files=@100.dat" | jq

# Générer un graphique
curl -X POST "http://localhost:8000/api/v1/signaux/plot/" \
  -F "signal_name=100" \
  -F "files=@100.hea" \
  -F "files=@100.dat" \
  -o ecg_plot.png

# Ouvrir l'image
xdg-open ecg_plot.png
```

### Exemple 4 : Analyse de rapports médicaux

```bash
# Analyser plusieurs rapports
curl -X POST "http://localhost:8000/api/v1/text/analyser_documents" \
  -F "files=@rapport1.docx" \
  -F "files=@rapport2.docx" \
  -F "files=@rapport3.txt" | jq

# Générer des annotations et télécharger en ZIP
curl -X POST "http://localhost:8000/api/v1/text/telecharger_annotations_zip" \
  -F "files=@donnees.csv" \
  -o annotations.zip
```

### Exemple 5 : Traitement par lots

```bash
# Créer une archive mixte
zip -r donnees_medicales.zip images/ signaux/ rapports/

# Traiter tout d'un coup
curl -X POST "http://localhost:8000/api/v1/batch/process_zip" \
  -F "file=@donnees_medicales.zip" \
  -o resultats_complets.zip

# Extraire et examiner
unzip resultats_complets.zip
cat processing_report.txt
```

### Exemple 6 : Surveillance des jobs

```javascript
// Interface web avec mise à jour automatique
async function processFiles(files) {
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));
  
  // Soumettre
  const submitRes = await fetch('/api/v1/images/preprocess_dicom_files_async/', {
    method: 'POST',
    body: formData
  });
  const { job_id } = await submitRes.json();
  
  // Créer barre de progression
  const progressBar = document.getElementById('progress');
  const statusText = document.getElementById('status');
  
  // Suivre
  const interval = setInterval(async () => {
    const statusRes = await fetch(`/jobs/${job_id}`);
    const status = await statusRes.json();
    
    progressBar.value = status.progress_percent;
    statusText.textContent = status.message;
    
    if (status.status === 'completed') {
      clearInterval(interval);
      statusText.textContent = '✓ Traitement terminé !';
      
      // Télécharger automatiquement
      window.location.href = `/api/v1/images/download_result/${job_id}`;
    } else if (status.status === 'failed') {
      clearInterval(interval);
      statusText.textContent = `✗ Erreur: ${status.error}`;
    }
  }, 2000);
}
```

---

## Support et Maintenance

### Logs et Debugging

**Vérifier les logs** :
```bash
# Si lancé en foreground : logs dans le terminal

# Si lancé en background :
tail -f /tmp/api.log
```

**Filtrer par ID de requête** :
```bash
grep "abc-123-def-456" /tmp/api.log
```

### Monitoring

**Vérifier la santé** :
```bash
curl http://localhost:8000/health
```

**Lister les jobs actifs** :
```bash
curl http://localhost:8000/jobs?status=processing
```

**Statistiques rate limiting** :
```bash
curl -i http://localhost:8000/api/v1/signaux/ | grep X-RateLimit
```

### Déploiement en production

**Checklist** :
- [ ] Configurer `ALLOWED_ORIGINS` avec domaines spécifiques
- [ ] Ajuster les limites de rate limiting selon besoins
- [ ] Configurer `API_BASE_URL` avec URL de production
- [ ] Activer l'agrégation de logs
- [ ] Mettre en place la surveillance `/health`
- [ ] Utiliser Redis pour le job tracking
- [ ] Configurer stockage cloud (S3) pour les résultats
- [ ] Activer HTTPS/TLS
- [ ] Configurer pare-feu
- [ ] Définir politiques de sauvegarde

**Lancement avec Gunicorn + Uvicorn** :
```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 600 \
  --access-logfile /var/log/api/access.log \
  --error-logfile /var/log/api/error.log
```

---

## Changelog

### Version 2.0.0 (2025-12-14)

**Nouvelles fonctionnalités** :
- ✅ Système de jobs asynchrones avec suivi en temps réel
- ✅ Rate limiting configurable
- ✅ Logging complet des requêtes avec ID unique
- ✅ Versioning de l'API (/api/v1/)
- ✅ Validation et sanitisation renforcées des entrées
- ✅ Gestion d'erreurs sécurisée
- ✅ Nettoyage automatique des fichiers temporaires

**Améliorations** :
- Protection contre les attaques XSS et traversée de chemin
- Endpoints health check et monitoring
- Documentation interactive enrichie
- Gestion CORS configurable
- Support multi-workers

**Breaking changes** :
- Aucun (rétrocompatibilité maintenue avec endpoints legacy)

### Version 1.1.0

- Ajout du traitement par lots
- Amélioration de l'anonymisation DICOM
- Support de formats supplémentaires pour les textes

### Version 1.0.0

- Version initiale
- Support DICOM, WFDB, documents textuels

---

## Licence et Contact

Cette API est développée pour le traitement de données médicales dans un cadre de recherche et d'enseignement.

**⚠️ Avertissement** : Cette API est fournie à des fins éducatives. Pour une utilisation en production dans un contexte médical réel, des certifications et validations supplémentaires sont nécessaires (conformité HIPAA, RGPD, etc.).

Pour toute question ou suggestion, consultez la documentation interactive à `/docs` ou contactez l'équipe de développement.

---

**Dernière mise à jour** : 14 décembre 2025  
**Version de l'API** : 2.0.0  
**Framework** : FastAPI  
**Auteur** : Équipe API Médicale
