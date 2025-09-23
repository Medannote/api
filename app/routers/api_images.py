import os
import pydicom
import nibabel as nib
import numpy as np
import pandas as pd
from skimage.transform import resize
from skimage import exposure
import shutil
import json
from datetime import datetime
from typing import List
from PIL import Image

from app.dependencies import *

from fastapi import FastAPI, Query, UploadFile, File, HTTPException, APIRouter
from fastapi.responses import StreamingResponse
import io

router = APIRouter()

# Fonctions de prétraitement du notebook (adaptées pour l'API)

@router.post("/preprocess_dicom_files/")
async def preprocess_dicom_files(
    files: List[UploadFile] = File(...),
    n: int = Query(256, description="hauteur de l'image"),
    m: int = Query(256, description="largeur de l'image")
      ):
    """
    Point de terminaison pour prétraiter un ou plusieurs fichiers DICOM.
    Anonymise, convertit en NIfTI, redimensionne, normalise, et renvoie une archive ZIP.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Aucun fichier n'a été téléchargé.")
        
    temp_dir = "temp_processing_dir"
    output_base_dir = os.path.join(temp_dir, "processed_data")
    
    # Nettoyer et recréer le répertoire temporaire pour chaque nouvelle requête
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(output_base_dir, exist_ok=True)

    nomenclature_entries = []
    
    # Initialisation des compteurs
    patient_counter = 1
    study_counter = 1
    series_counter = 1

    for file in files:
        temp_dicom_path = os.path.join(temp_dir, file.filename)
        try:
            with open(temp_dicom_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception:
            raise HTTPException(status_code=500, detail=f"Erreur lors de la sauvegarde du fichier : {file.filename}.")

        try:
            dicom_data = pydicom.dcmread(temp_dicom_path)
        except Exception:
            os.remove(temp_dicom_path)
            raise HTTPException(status_code=400, detail=f"Le fichier {file.filename} n'est pas un fichier DICOM valide.")

        # Extraire les métadonnées originales
        original_patient_id = str(dicom_data.get('PatientID', ''))
        original_study_id = str(dicom_data.get('StudyID', ''))
        original_modality = str(dicom_data.get('Modality', ''))
        original_study_date = str(dicom_data.get('StudyDate', ''))
        original_study_desc = str(dicom_data.get('StudyDescription', ''))
        original_study_time = str(dicom_data.get('StudyTime', ''))

        # Anonymiser les données
        anonymized_dicom = anonymize_dicom(dicom_data)
        
        # Convertir en NIfTI et prétraiter
        conversion_result = convert_dicom_to_nifti(
            anonymized_dicom,
            f"P{patient_counter:03d}",
            f"S{study_counter:03d}",
            f"SE{series_counter:03d}"
        )

        if not conversion_result:
            raise HTTPException(status_code=500, detail=f"Erreur lors de la conversion ou du prétraitement pour le fichier {file.filename}.")

        image_data = conversion_result['pixel_array']
        nifti_img = conversion_result['nifti_img']
        metadata = conversion_result['metadata']

        # Appliquer le prétraitement
        try:
            resized_image = resize_image(image_data, target_size=(n, m))
            normalized_image = normalize_image(resized_image)
            enhanced_image = apply_histogram_equalization(normalized_image)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur lors du prétraitement de l'image {file.filename} : {e}")

        # Sauvegarder l'image prétraitée
        processed_nifti = nib.Nifti1Image(enhanced_image, nifti_img.affine)
        images_dir = os.path.join(output_base_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        processed_filename = f"processed_PAT_{patient_counter:03d}_ST_{study_counter:03d}_SE_{series_counter:03d}.nii.gz"
        processed_filepath = os.path.join(images_dir, processed_filename)
        nib.save(processed_nifti, processed_filepath)

        # Sauvegarder les métadonnées
        metadata_dir = os.path.join(output_base_dir, "metadata")
        os.makedirs(metadata_dir, exist_ok=True)
        metadata_filename = f"metadata_P{patient_counter:03d}_S{study_counter:03d}_SE{series_counter:03d}.json"
        metadata_filepath = os.path.join(metadata_dir, metadata_filename)
        with open(metadata_filepath, 'w') as f:
            json.dump(metadata, f, indent=4)

        # Sauvegarder le fichier .hdr (métadonnées DICOM complètes)
        hdr_dir = os.path.join(output_base_dir, "metadata_hdr")
        os.makedirs(hdr_dir, exist_ok=True)
        hdr_filename = f"metadata_P{patient_counter:03d}_S{study_counter:03d}_SE{series_counter:03d}.hdr"
        hdr_filepath = os.path.join(hdr_dir, hdr_filename)
        with open(hdr_filepath, 'w', encoding='utf-8') as f:
            f.write(conversion_result['hdr_content'])

        # Ajouter l'entrée de nomenclature
        nomenclature_entry = {
            'patient_id_nomenclature': f"P{patient_counter:03d}",
            'study_id_nomenclature': f"S{study_counter:03d}",
            'series_id_nomenclature': f"SE{series_counter:03d}",
            'original_patient_id': original_patient_id,
            'original_study_id': original_study_id,
            'original_modality': original_modality,
            'original_study_date': original_study_date,
            'Study_Description': original_study_desc,
            'Study_Time': original_study_time
        }
        nomenclature_entries.append(nomenclature_entry)

        # Incrémenter les compteurs pour le prochain fichier
        patient_counter += 1
        study_counter += 1
        series_counter += 1

    # Créer le fichier CSV de nomenclature unique
    csv_dir = os.path.join(output_base_dir, "csv_files")
    os.makedirs(csv_dir, exist_ok=True)
    df = pd.DataFrame(nomenclature_entries)
    csv_filename = os.path.join(csv_dir, "nomenclature_mapping.csv")
    df.to_csv(csv_filename, index=False)

    # Créer l'archive ZIP
    zip_path = os.path.join(temp_dir, "processed_medical_images")
    shutil.make_archive(zip_path, 'zip', output_base_dir)

    # Préparer le fichier zip pour le streaming
    zip_file_path = f"{zip_path}.zip"
    
    # Lire le fichier zip en mémoire pour le renvoyer
    zip_buffer = io.BytesIO()
    with open(zip_file_path, "rb") as f:
        zip_buffer.write(f.read())
    zip_buffer.seek(0)

    # Nettoyer les fichiers temporaires
    shutil.rmtree(temp_dir)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={os.path.basename(zip_file_path)}"}
    )