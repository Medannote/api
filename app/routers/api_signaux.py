from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, APIRouter
from fastapi.responses import JSONResponse, StreamingResponse


import wfdb
import pandas as pd
import os
import numpy as np
import glob
import uuid
import tempfile
import zipfile
import io
from typing import List, Dict, Optional
from pathlib import Path

from app.dependencies import *

router = APIRouter()

# Endpoints de l'API
@router.get("/")
async def root():
    """Point d'entrée de l'API"""
    return {
        "message": "API de Traitement de Signaux Médicaux",
        "version": "1.0.0",
        "endpoints": {
            "metadata": "POST /metadata/ - Récupère les métadonnées d'un signal",
            "plot_signal": "POST /plot/ - Génère un graphique du signal",
            "process_folder": "POST /process_folder - Traite tous les signaux d'un dossier",
            "download_metadata": "POST /download_metadata - Télécharge les métadonnées en format CSV"
        }
    }

@router.post("/metadata/")
async def get_metadata(background_tasks: BackgroundTasks, signal_name: str, files: List[UploadFile] = File(...)):
    """
    Récupère les métadonnées d'un signal spécifique à partir de fichiers uploadés
    """
    # Validate uploaded files
    await validate_file_upload(files, allowed_extensions=ALLOWED_SIGNAL_EXTENSIONS)

    try:
        temp_dir = tempfile.mkdtemp()
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
        full_path = os.path.join(temp_dir, signal_name)
        metadata = afficher_toutes_metadonnées(full_path)

        def remove_temp_files():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        background_tasks.add_task(remove_temp_files)

        return {"signal_name": signal_name, "metadata": metadata}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/plot/")
async def get_signal_plot(background_tasks: BackgroundTasks, signal_name: str, files: List[UploadFile] = File(...)):
    """
    Génère et retourne un graphique du signal spécifié à partir de fichiers uploadés
    """
    # Validate uploaded files
    await validate_file_upload(files, allowed_extensions=ALLOWED_SIGNAL_EXTENSIONS)

    try:
        temp_dir = tempfile.mkdtemp()
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
        full_path = os.path.join(temp_dir, signal_name)
        image_buffer = plot_signal(full_path)

        def remove_temp_files():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        background_tasks.add_task(remove_temp_files)

        return StreamingResponse(
            image_buffer,
            media_type="image/png",
            headers={"Content-Disposition": f"attachment; filename={signal_name}_plot.png"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process_folder")
async def process_folder(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """
    Traite tous les signaux uploadés et retourne les métadonnées
    """
    # Validate uploaded files
    await validate_file_upload(files, allowed_extensions=ALLOWED_SIGNAL_EXTENSIONS)

    try:
        temp_dir = tempfile.mkdtemp()
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
        df = stocker_csv(temp_dir)
        personal_df, medical_df = division_df(temp_dir)

        def remove_temp_files():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        background_tasks.add_task(remove_temp_files)

        return {
            "total_signals": len(df),
            "personal_info": personal_df.to_dict(orient='records'),
            "medical_metadata": medical_df.to_dict(orient='records'),
            "full_metadata": df.to_dict(orient='records')
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/download_metadata")
async def download_metadata(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """
    Télécharge toutes les métadonnées des signaux uploadés sous forme de fichiers CSV dans un ZIP
    """
    # Validate uploaded files
    await validate_file_upload(files, allowed_extensions=ALLOWED_SIGNAL_EXTENSIONS)

    try:
        temp_dir = tempfile.mkdtemp()
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
        zip_path = os.path.join(temp_dir, "metadata.zip")
        personal_df, medical_df = division_df(temp_dir)

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            personal_csv = io.StringIO()
            personal_df.to_csv(personal_csv, index=False)
            zipf.writestr("informations_personnelles.csv", personal_csv.getvalue())

            medical_csv = io.StringIO()
            medical_df.to_csv(medical_csv, index=False)
            zipf.writestr("metadonnees_medicales.csv", medical_csv.getvalue())

            readme_content = """# Métadonnées de Signaux Médicaux

## Fichiers inclus:
- informations_personnelles.csv : Informations d'identification des patients
- metadonnees_medicales.csv : Métadonnées techniques des signaux

## Structure des données:

### Informations personnelles:
- signal_name: Nom du fichier signal
- id: Identifiant unique du patient
- nom, prenom, age: Informations personnelles (si disponibles)

### Métadonnées médicales:
- Toutes les autres métadonnées techniques du signal
"""
            zipf.writestr("README.md", readme_content)

        # Lire le fichier ZIP en mémoire
        with open(zip_path, "rb") as f:
            zip_data = io.BytesIO(f.read())
        zip_data.seek(0)

        def remove_temp_files():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        background_tasks.add_task(remove_temp_files)

        return StreamingResponse(
            zip_data,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=metadata_signaux_medicaux.zip"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload_signals")
async def upload_signals(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """
    Upload de fichiers de signaux médicaux (.hea et .dat) et traitement
    """
    # Validate uploaded files
    await validate_file_upload(files, allowed_extensions=ALLOWED_SIGNAL_EXTENSIONS)

    try:
        # Créer un répertoire temporaire
        temp_dir = tempfile.mkdtemp()
        
        # Sauvegarder tous les fichiers uploadés
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
        
        # Traiter les fichiers
        df = stocker_csv(temp_dir)
        personal_df, medical_df = division_df(temp_dir)
        
        # Nettoyer les fichiers temporaires après traitement
        def remove_temp_files():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        background_tasks.add_task(remove_temp_files)
        
        return {
            "uploaded_files": [file.filename for file in files],
            "total_signals": len(df),
            "personal_info": personal_df.to_dict(orient='records'),
            "medical_metadata": medical_df.to_dict(orient='records')
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))