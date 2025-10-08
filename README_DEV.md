# Guide Développeur

## Structure du Projet

```
functional_api/
├── app/
│   ├── __init__.py
│   ├── main.py              # Application FastAPI principale
│   ├── dependencies.py      # Dépendances et utilitaires partagés
│   └── routers/
│       ├── api_images.py    # Endpoints de traitement d'images/DICOM
│       ├── api_signaux.py   # Endpoints de traitement de signaux/WFDB
│       └── api_text.py      # Endpoints de traitement de texte/documents
├── .venv/                   # Environnement virtuel (non commité)
├── requirements.txt         # Dépendances Python
├── .gitignore              # Règles d'exclusion Git
├── Readme.md               # Documentation utilisateur principale
└── README_DEV.md           # Ce fichier - documentation développeur
```

## Configuration de l'Environnement de Développement

### 1. Cloner le Dépôt

```bash
git clone <url-du-depot>
cd functional_api
```

### 2. Créer un Environnement Virtuel

```bash
python3 -m venv .venv
source .venv/bin/activate  # Sur Linux/Mac
# .venv\Scripts\activate   # Sur Windows
```

### 3. Installer les Dépendances

```bash
pip install -r requirements.txt
```

### 4. Variables d'Environnement

Créer un fichier `.env` à la racine du projet si nécessaire :

```bash
# Exemple de variables d'environnement
# API_KEY=votre_cle_api_ici
# DATABASE_URL=sqlite:///./test.db
# DEBUG=True
```

> **Note :** Le fichier `.env` est ignoré par git pour protéger les informations sensibles.

## Dépendances Principales

- **FastAPI** - Framework web moderne pour construire des APIs
- **Uvicorn** - Serveur ASGI pour exécuter FastAPI
- **pydicom** - Support du format d'imagerie médicale DICOM
- **nibabel** - Formats de données de neuroimagerie (NIfTI)
- **wfdb** - Traitement de signaux physiologiques (format WFDB)
- **pandas** - Manipulation et analyse de données
- **scikit-image** - Traitement d'images
- **python-docx** - Traitement de documents Microsoft Word
- **nltk** - Traitement du langage naturel

## Exécution en Mode Développement

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Le flag `--reload` active le redémarrage automatique lors des modifications du code.

## Tests

### Tests Manuels avec Swagger UI

Visitez `http://localhost:8000/docs` pour la documentation interactive de l'API.

### Tests Automatisés (Exemple)

```bash
# Installer pytest s'il n'est pas déjà installé
pip install pytest pytest-asyncio httpx

# Exécuter les tests
pytest tests/
```

## Considérations de Sécurité

### Configuration CORS

Les paramètres CORS de l'API sont configurés dans [app/main.py](app/main.py). Examinez et ajustez les origines autorisées pour la production :

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ À changer pour la production !
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Anonymisation des Données

- Les images médicales sont automatiquement anonymisées via l'endpoint `/images/preprocess_dicom_files/`
- Des identifiants uniques sont générés pour les données patients afin de protéger la confidentialité
- Examinez la logique d'anonymisation dans [app/routers/api_images.py](app/routers/api_images.py)

### Sécurité des Téléchargements de Fichiers

- Valider les types et tailles de fichiers avant le traitement
- Les fichiers temporaires sont nettoyés après traitement
- Envisagez d'implémenter des limites de taille de fichier en production

## Problèmes Courants et Dépannage

### Port Déjà Utilisé

```bash
# Trouver le processus utilisant le port 8000
lsof -i :8000

# Tuer le processus ou utiliser un port différent
uvicorn app.main:app --reload --port 8001
```

### Données NLTK Manquantes

Si vous rencontrez des erreurs NLTK, téléchargez les données requises :

```python
import nltk
nltk.download('punkt')
nltk.download('stopwords')
```

### Erreurs d'Importation

Assurez-vous que votre environnement virtuel est activé et que les dépendances sont installées :

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Erreurs de Traitement DICOM

- Vérifiez que les fichiers DICOM sont valides en utilisant une visionneuse DICOM
- Vérifiez les permissions et chemins des fichiers
- Consultez les logs pour des erreurs pydicom spécifiques

## Directives de Contribution

### Style de Code

- Suivez les directives de style PEP 8
- Utilisez des noms de variables et de fonctions significatifs
- Ajoutez des docstrings aux fonctions et classes
- Gardez les fonctions ciblées et modulaires

### Workflow Git

1. Créer une branche de fonctionnalité : `git checkout -b feature/nom-de-votre-fonctionnalite`
2. Effectuer vos modifications et commiter : `git commit -m "Ajouter description de la fonctionnalité"`
3. Pousser vers le dépôt distant : `git push origin feature/nom-de-votre-fonctionnalite`
4. Créer une pull request pour révision

### Format des Messages de Commit

```
<type>: <résumé court>

<description détaillée optionnelle>

Exemples:
- feat: Ajouter export CSV pour les métadonnées de signaux
- fix: Résoudre le bug d'anonymisation DICOM
- docs: Mettre à jour la documentation des endpoints API
- refactor: Simplifier la logique d'extraction de texte
```

## Conseils de Développement API

### Ajouter un Nouvel Endpoint

1. Choisir le fichier router approprié dans [app/routers/](app/routers/)
2. Définir la fonction endpoint avec les annotations de type appropriées
3. Ajouter la validation d'entrée en utilisant les modèles Pydantic
4. Implémenter la gestion des erreurs avec les codes de statut HTTP appropriés
5. Mettre à jour la documentation dans [Readme.md](Readme.md)

### Bonnes Pratiques de Gestion des Erreurs

```python
from fastapi import HTTPException

@app.post("/example")
async def example_endpoint(file: UploadFile):
    if not file:
        raise HTTPException(status_code=400, detail="Aucun fichier fourni")

    try:
        # Traiter le fichier
        result = process_file(file)
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")
```

## Optimisation des Performances

- Utiliser async/await pour les opérations I/O
- Implémenter le streaming pour les réponses de fichiers volumineux
- Envisager la mise en cache pour les données fréquemment consultées
- Profiler le code pour identifier les goulots d'étranglement

## Considérations de Déploiement

### Serveur de Production

Utiliser un serveur ASGI de qualité production avec plusieurs workers :

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Ou utiliser Gunicorn avec des workers Uvicorn :

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Déploiement Docker (Exemple)

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Ressources Supplémentaires

- [Documentation FastAPI](https://fastapi.tiangolo.com/)
- [Documentation Uvicorn](https://www.uvicorn.org/)
- [Annotations de Type Python](https://docs.python.org/fr/3/library/typing.html)

## Licence

[Ajoutez vos informations de licence ici]

## Support

Pour des questions ou problèmes :

- Ouvrir une issue sur le dépôt
- Contacter l'équipe de développement
- Consulter la documentation existante dans [Readme.md](Readme.md)
