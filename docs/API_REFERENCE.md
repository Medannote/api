# API Médicale Unifiée - Référence Complète

> **Version**: 2.0.0  
> **Base URL**: `https://apiannote.leapcell.app`  
> **Documentation Interactive**: [Swagger UI](https://apiannote.leapcell.app/docs)

---

## Table des Matières

- [Authentification](#authentification)
- [Rate Limiting](#rate-limiting)
- [Endpoints Système](#endpoints-système)
- [Module Images DICOM](#module-images-dicom)
- [Module Signaux Médicaux](#module-signaux-médicaux)
- [Module Textes Médicaux](#module-textes-médicaux)
- [Module Traitement par Lots](#module-traitement-par-lots)
- [Gestion des Jobs Asynchrones](#gestion-des-jobs-asynchrones)
- [Codes d'Erreur](#codes-derreur)
- [Exemples cURL](#exemples-curl)

---

## Authentification

L'API est actuellement ouverte. Aucune authentification requise.

---

## Rate Limiting

| Header | Description |
|--------|-------------|
| `X-Ratelimit-Limit` | Nombre maximum de requêtes par période |
| `X-Ratelimit-Remaining` | Requêtes restantes |
| `X-Ratelimit-Reset` | Timestamp de réinitialisation |

**Limites par défaut**: 100 requêtes / 60 secondes

---

## Endpoints Système

### GET `/`

Informations de base de l'API.

**Réponse** `200 OK`:
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

---

### GET `/health`

Vérification de l'état de santé de l'API.

**Réponse** `200 OK`:
```json
{
  "status": "healthy",
  "service": "API Médicale Unifiée",
  "version": "2.0.0"
}
```

---

### GET `/docs`

Interface Swagger UI pour tester l'API de manière interactive.

---

### GET `/openapi.json`

Spécification OpenAPI 3.1 complète au format JSON.

---

## Module Images DICOM

### POST `/api/v1/images/preprocess_dicom_files/`

Prétraitement synchrone de fichiers DICOM. Anonymise, convertit en NIfTI, redimensionne et normalise.

**Paramètres Query**:
| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `n` | integer | 256 | Hauteur de l'image cible |
| `m` | integer | 256 | Largeur de l'image cible |

**Corps de la requête** `multipart/form-data`:
| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `files` | file[] | ✅ | Fichiers DICOM (.dcm, .dicom) |

**Réponse** `200 OK`:
- Content-Type: `application/zip`
- Fichier ZIP contenant:
  - `images/` - Images NIfTI prétraitées (.nii.gz)
  - `metadata/` - Métadonnées JSON
  - `metadata_hdr/` - En-têtes DICOM complets (.hdr)
  - `csv_files/nomenclature_mapping.csv` - Table de correspondance

**Exemple cURL**:
```bash
curl -X POST "https://apiannote.leapcell.app/api/v1/images/preprocess_dicom_files/?n=512&m=512" \
  -F "files=@scan1.dcm" \
  -F "files=@scan2.dcm" \
  --output results.zip
```

---

### POST `/api/v1/images/preprocess_dicom_files_async/`

Version asynchrone du prétraitement DICOM. Retourne immédiatement un `job_id`.

**Paramètres**: Identiques à la version synchrone.

**Réponse** `200 OK`:
```json
{
  "job_id": "img_abc123def456",
  "status": "pending",
  "message": "Traitement démarré",
  "check_status_url": "/jobs/img_abc123def456"
}
```

---

### GET `/api/v1/images/download_result/{job_id}`

Télécharge le résultat d'un job terminé.

**Paramètres Path**:
| Paramètre | Type | Description |
|-----------|------|-------------|
| `job_id` | string | Identifiant du job |

**Réponse** `200 OK`:
- Content-Type: `application/zip`

**Réponse** `404 Not Found`:
```json
{
  "detail": "Le fichier résultat n'est plus disponible."
}
```

---

### POST `/api/v1/images/convert_dicom_for_viewer`

Convertit un fichier DICOM en format affichable (PNG base64) avec métadonnées.

**Corps de la requête** `multipart/form-data`:
| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `file` | file | ✅ | Fichier DICOM unique |

**Réponse** `200 OK`:
```json
{
  "image": "data:image/png;base64,iVBORw0KGgo...",
  "metadata": {
    "patient_name": "Anonymized",
    "patient_id": "P001",
    "modality": "CT",
    "study_date": "20260115",
    "dimensions": [512, 512],
    "pixel_spacing": [0.5, 0.5]
  }
}
```

---

## Module Signaux Médicaux

### GET `/api/v1/signaux/`

Informations sur le module de traitement des signaux.

**Réponse** `200 OK`:
```json
{
  "message": "API de Traitement de Signaux Médicaux",
  "version": "1.0.0",
  "endpoints": {
    "metadata": "POST /metadata/",
    "plot_signal": "POST /plot/",
    "process_folder": "POST /process_folder",
    "download_metadata": "POST /download_metadata"
  }
}
```

---

### POST `/api/v1/signaux/metadata/`

Récupère les métadonnées d'un signal spécifique.

**Paramètres Query**:
| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `signal_name` | string | ✅ | Nom du signal (sans extension) |

**Corps de la requête** `multipart/form-data`:
| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `files` | file[] | ✅ | Fichiers .hea et .dat correspondants |

**Réponse** `200 OK`:
```json
{
  "signal_name": "patient_ecg",
  "fs": 360,
  "n_sig": 2,
  "sig_len": 650000,
  "comments": ["Recording: 24h Holter"],
  "units": ["mV", "mV"]
}
```

---

### POST `/api/v1/signaux/plot/`

Génère un graphique PNG du signal.

**Paramètres Query**:
| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `signal_name` | string | ✅ | Nom du signal |

**Corps de la requête** `multipart/form-data`:
| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `files` | file[] | ✅ | Fichiers .hea et .dat |

**Réponse** `200 OK`:
- Content-Type: `image/png`

---

### POST `/api/v1/signaux/process_folder`

Traite plusieurs signaux et retourne toutes les métadonnées.

**Corps de la requête** `multipart/form-data`:
| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `files` | file[] | ✅ | Tous les fichiers .hea et .dat |

**Réponse** `200 OK`:
```json
{
  "count": 5,
  "signals": [
    {"signal_name": "ecg_001", "fs": 360, "duration": 3600},
    {"signal_name": "ecg_002", "fs": 500, "duration": 1800}
  ]
}
```

---

### POST `/api/v1/signaux/download_metadata`

Télécharge les métadonnées de tous les signaux en ZIP (CSV).

**Corps de la requête** `multipart/form-data`:
| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `files` | file[] | ✅ | Fichiers de signaux |

**Réponse** `200 OK`:
- Content-Type: `application/zip`
- Contenu: `metadata.csv`, `personal_info.csv`

---

### POST `/api/v1/signaux/convert_signal_for_viewer`

Convertit les signaux en format JSON pour affichage web.

**Corps de la requête** `multipart/form-data`:
| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `files` | file[] | ✅ | Fichiers .hea et .dat |

**Réponse** `200 OK`:
```json
{
  "signal_data": [[0, 0.5], [1, 0.7], [2, 0.3]],
  "metadata": {
    "record_name": "ecg_001",
    "sampling_frequency": 360,
    "duration": 10.5,
    "n_signals": 2,
    "signal_names": ["MLII", "V1"]
  }
}
```

---

### POST `/api/v1/signaux/upload_signals`

Upload et traitement de fichiers de signaux médicaux.

**Corps de la requête** `multipart/form-data`:
| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `files` | file[] | ✅ | Fichiers .hea et .dat |

**Réponse** `200 OK`:
```json
{
  "status": "success",
  "processed_signals": 3,
  "results": [...]
}
```

---

## Module Textes Médicaux

### GET `/api/v1/text/`

Informations sur le module de traitement de texte.

---

### GET `/api/v1/text/sante`

Vérification de santé du module texte.

**Réponse** `200 OK`:
```json
{
  "statut": "OK",
  "message": "L'API fonctionne correctement",
  "timestamp": "2026-01-18T11:21:19.633286"
}
```

---

### POST `/api/v1/text/analyser_documents`

Analyse plusieurs documents médicaux et extrait les informations structurées.

**Corps de la requête** `multipart/form-data`:
| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `files` | file[] | ✅ | Documents (.docx, .txt) |

**Réponse** `200 OK`:
```json
{
  "nombre_fichiers": 2,
  "resultats": [
    {
      "filename": "rapport_patient1.docx",
      "status": "success",
      "donnees_extraites": {
        "Nom": "Dupont",
        "Prénom": "Jean",
        "Age": 45,
        "Date": "15 janvier 2026",
        "Symptômes": "douleur thoracique",
        "Diagnostic": "angine poitrine",
        "Traitement": "aspirine nitroglycérine"
      }
    }
  ],
  "donnees_combinees": [...]
}
```

**Formats supportés**:
- `.docx` - Documents Word
- `.txt` - Fichiers texte

---

### POST `/api/v1/text/generer_annotations`

Génère des annotations et identifiants uniques pour les données médicales.

**Corps de la requête** `multipart/form-data`:
| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `files` | file[] | ✅ | Documents ou fichiers de données |

**Réponse** `200 OK`:
```json
{
  "nombre_fichiers": 1,
  "resultats": [
    {
      "filename": "patients.csv",
      "status": "success",
      "df_personnel": [
        {"Nom": "Dupont", "Prénom": "Jean", "Année de naissance": 1981, "ID d'annotation": 26011810451}
      ],
      "df_medical": [
        {"ID d'annotation": 26011810451, "Symptômes": "...", "Diagnostic": "..."}
      ]
    }
  ]
}
```

**Structure de l'ID d'annotation (11 chiffres)**:
- `AA` (2): Année
- `MM` (2): Mois
- `JJ` (2): Jour
- `S` (1): Sexe (0=Homme, 1=Femme)
- `AGE` (3): Âge sur 3 chiffres
- `D` (1): Diagnostic (0=Normal, 1=Pathologique)

---

### POST `/api/v1/text/telecharger_annotations_zip`

Génère les annotations et retourne un ZIP avec tous les résultats.

**Corps de la requête** `multipart/form-data`:
| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `files` | file[] | ✅ | Fichiers de données médicales |

**Réponse** `200 OK`:
- Content-Type: `application/zip`
- Contenu:
  - `donnees_personnelles.csv/.xlsx/.json`
  - `donnees_medicales.csv/.xlsx/.json`
  - `README.md`

---

### POST `/api/v1/text/supprimer_colonnes_zip`

Supprime des colonnes spécifiques de fichiers de données.

**Corps de la requête** `multipart/form-data`:
| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `colonnes_a_supprimer` | string[] | ✅ | Noms des colonnes à supprimer |
| `files` | file[] | ✅ | Fichiers de données |

**Note**: La colonne `ID d'annotation` est protégée et ne peut pas être supprimée.

**Réponse** `200 OK`:
- Content-Type: `application/zip`
- Fichiers modifiés avec suffixe `_modifie`

---

## Module Traitement par Lots

### GET `/api/v1/batch/`

Informations sur le module de traitement par lots.

**Réponse** `200 OK`:
```json
{
  "message": "Batch Processing API",
  "version": "1.0.0",
  "endpoint": "/batch/process_zip",
  "description": "Process ZIP files containing mixed medical data types",
  "supported_types": {
    "images": [".dcm", ".dicom"],
    "signals": [".qrs", ".edf", ".hea", ".eeg", ".dat"],
    "text": [".docx", ".txt", ".csv", ".json", ".xlsx"]
  },
  "limits": {
    "max_files": 1000,
    "max_size_mb": 500,
    "max_compression_ratio": 100
  }
}
```

---

### POST `/api/v1/batch/process_zip`

Traite un fichier ZIP contenant des données médicales mixtes.

**Corps de la requête** `multipart/form-data`:
| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `file` | file | ✅ | Fichier ZIP contenant les données |

**Réponse** `200 OK`:
- Content-Type: `application/zip`
- Structure du ZIP de sortie:
  - `images_results.zip` (si fichiers DICOM trouvés)
  - `signals_results.zip` (si fichiers de signaux trouvés)
  - `text_results.zip` (si fichiers texte trouvés)
  - `processing_report.txt` (résumé du traitement)

**Exemple cURL**:
```bash
curl -X POST "https://apiannote.leapcell.app/api/v1/batch/process_zip" \
  -F "file=@medical_data.zip" \
  --output processed_results.zip
```

---

## Gestion des Jobs Asynchrones

### GET `/jobs`

Liste tous les jobs récents.

**Paramètres Query**:
| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `status` | string | null | Filtrer par statut |
| `limit` | integer | 50 | Nombre maximum de résultats |

**Statuts possibles**:
- `pending` - En attente
- `processing` - En cours
- `completed` - Terminé
- `failed` - Échoué
- `cancelled` - Annulé

**Réponse** `200 OK`:
```json
{
  "total": 3,
  "jobs": [
    {
      "job_id": "img_abc123",
      "status": "completed",
      "progress": 100,
      "message": "Traitement terminé",
      "created_at": "2026-01-18T10:00:00",
      "completed_at": "2026-01-18T10:05:32"
    }
  ]
}
```

---

### GET `/jobs/{job_id}`

Récupère le statut détaillé d'un job.

**Paramètres Path**:
| Paramètre | Type | Description |
|-----------|------|-------------|
| `job_id` | string | Identifiant du job |

**Réponse** `200 OK`:
```json
{
  "job_id": "img_abc123",
  "status": "processing",
  "progress": 45,
  "message": "Traitement du fichier 5/10: scan_005.dcm",
  "created_at": "2026-01-18T10:00:00",
  "result_path": null
}
```

**Réponse** `404 Not Found`:
```json
{
  "detail": "Job non trouvé. Il a peut-être expiré ou n'existe pas."
}
```

---

### DELETE `/jobs/{job_id}`

Annule ou supprime un job.

**Paramètres Path**:
| Paramètre | Type | Description |
|-----------|------|-------------|
| `job_id` | string | Identifiant du job |

**Réponse** `200 OK`:
```json
{
  "message": "Job annulé avec succès",
  "job_id": "img_abc123"
}
```

---

## Codes d'Erreur

| Code | Description |
|------|-------------|
| `200` | Succès |
| `400` | Requête invalide (fichier manquant, format non supporté) |
| `404` | Ressource non trouvée (job inexistant, fichier expiré) |
| `413` | Fichier trop volumineux |
| `422` | Erreur de validation des paramètres |
| `429` | Rate limit dépassé |
| `500` | Erreur interne du serveur |

**Format des erreurs**:
```json
{
  "detail": "Description de l'erreur"
}
```

**Erreurs de validation (422)**:
```json
{
  "detail": [
    {
      "loc": ["body", "files"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Exemples cURL

### Prétraiter des images DICOM

```bash
# Synchrone
curl -X POST "https://apiannote.leapcell.app/api/v1/images/preprocess_dicom_files/" \
  -F "files=@scan1.dcm" \
  -F "files=@scan2.dcm" \
  --output results.zip

# Asynchrone
curl -X POST "https://apiannote.leapcell.app/api/v1/images/preprocess_dicom_files_async/" \
  -F "files=@scan1.dcm" \
  -F "files=@scan2.dcm"

# Vérifier le statut
curl "https://apiannote.leapcell.app/jobs/img_abc123"

# Télécharger le résultat
curl "https://apiannote.leapcell.app/api/v1/images/download_result/img_abc123" \
  --output results.zip
```

### Analyser des signaux ECG

```bash
# Récupérer les métadonnées
curl -X POST "https://apiannote.leapcell.app/api/v1/signaux/metadata/?signal_name=patient_ecg" \
  -F "files=@patient_ecg.hea" \
  -F "files=@patient_ecg.dat"

# Générer un graphique
curl -X POST "https://apiannote.leapcell.app/api/v1/signaux/plot/?signal_name=patient_ecg" \
  -F "files=@patient_ecg.hea" \
  -F "files=@patient_ecg.dat" \
  --output signal_plot.png
```

### Analyser des documents médicaux

```bash
# Extraire les informations
curl -X POST "https://apiannote.leapcell.app/api/v1/text/analyser_documents" \
  -F "files=@rapport_patient.docx"

# Générer des annotations
curl -X POST "https://apiannote.leapcell.app/api/v1/text/telecharger_annotations_zip" \
  -F "files=@patients.csv" \
  --output annotations.zip
```

### Traitement par lots

```bash
curl -X POST "https://apiannote.leapcell.app/api/v1/batch/process_zip" \
  -F "file=@medical_archive.zip" \
  --output processed.zip
```

---

## Endpoints Legacy

Les endpoints suivants sont maintenus pour la compatibilité mais sont dépréciés. Utilisez les versions `/api/v1/` à la place.

| Legacy | Nouveau |
|--------|---------|
| `/images/*` | `/api/v1/images/*` |
| `/signaux/*` | `/api/v1/signaux/*` |
| `/text/*` | `/api/v1/text/*` |
| `/batch/*` | `/api/v1/batch/*` |

---

## Support

- **Documentation Interactive**: https://apiannote.leapcell.app/docs
- **Spécification OpenAPI**: https://apiannote.leapcell.app/openapi.json
- **Health Check**: https://apiannote.leapcell.app/health

---

*Dernière mise à jour: 18 janvier 2026*
