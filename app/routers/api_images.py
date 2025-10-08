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
import tempfile
import zipfile
import io

from app.dependencies import *

from fastapi import FastAPI, Query, UploadFile, File, HTTPException, APIRouter, Form, BackgroundTasks
from fastapi.responses import StreamingResponse

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
    # Validate uploaded files
    await validate_file_upload(files, allowed_extensions=ALLOWED_DICOM_EXTENSIONS)

    # Créer un répertoire temporaire sécurisé
    temp_dir = tempfile.mkdtemp()
    output_base_dir = os.path.join(temp_dir, "processed_data")
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

    # Nettoyer les fichiers temporaires immédiatement après lecture
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass  # Ignore cleanup errors

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={os.path.basename(zip_file_path)}"}
    )


@router.post("/supprimer_colonnes_zip/")
async def supprimer_colonnes_zip(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    metadata_to_remove: List[str] = Form(None, description="Liste des métadonnées supplémentaires à supprimer"),
    n: int = Query(256, description="hauteur de l'image"),
    m: int = Query(256, description="largeur de l'image")
):
    """
    Point de terminaison pour prétraiter des fichiers DICOM avec suppression de métadonnées supplémentaires.
    Anonymise, supprime les métadonnées spécifiées, convertit en NIfTI, et renvoie une archive ZIP.
    """
    # Validate uploaded files
    await validate_file_upload(files, allowed_extensions=ALLOWED_DICOM_EXTENSIONS)
    
    # Métadonnées à supprimer par défaut (celles de la fonction anonymize_dicom)
    default_tags_to_remove = [
        (0x0010, 0x0010), (0x0010, 0x0020), (0x0010, 0x0030), (0x0010, 0x0040),
        (0x0010, 0x1000), (0x0010, 0x1001), (0x0010, 0x2160), (0x0008, 0x0020),
        (0x0008, 0x0030), (0x0008, 0x0090), (0x0008, 0x1050), (0x0008, 0x1080)
    ]
    
    # Convertir les noms de métadonnées en tags DICOM si des métadonnées supplémentaires sont spécifiées
    additional_tags_to_remove = []
    if metadata_to_remove:
        tag_mapping = {
            'PatientName': (0x0010, 0x0010),
            'PatientID': (0x0010, 0x0020),
            'PatientBirthDate': (0x0010, 0x0030),
            'PatientSex': (0x0010, 0x0040),
            'StudyDate': (0x0008, 0x0020),
            'StudyTime': (0x0008, 0x0030),
            'ReferringPhysicianName': (0x0008, 0x0090),
            'StudyDescription': (0x0008, 0x1030),
            'SeriesDescription': (0x0008, 0x103E),
            'InstitutionName': (0x0008, 0x0080),
            'InstitutionAddress': (0x0008, 0x0081)
        }
        
        for metadata_name in metadata_to_remove:
            if metadata_name in tag_mapping:
                additional_tags_to_remove.append(tag_mapping[metadata_name])
    
    # Combiner les tags à supprimer
    all_tags_to_remove = default_tags_to_remove + additional_tags_to_remove
    
    def anonymize_dicom_advanced(dicom_data: pydicom.dataset.FileDataset) -> pydicom.dataset.FileDataset:
        """Anonymise les données sensibles avec suppression de métadonnées supplémentaires."""
        anonymized_dicom = dicom_data.copy()
        for tag in all_tags_to_remove:
            if tag in anonymized_dicom:
                del anonymized_dicom[tag]
        anonymized_dicom.InstitutionName = "Anonymized Healthcare Facility"
        return anonymized_dicom

    # Créer un répertoire temporaire
    temp_dir = tempfile.mkdtemp()
    output_base_dir = os.path.join(temp_dir, "processed_data_anonymized")
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

        # Extraire les métadonnées originales pour la nomenclature
        original_patient_id = str(dicom_data.get('PatientID', ''))
        original_study_id = str(dicom_data.get('StudyID', ''))
        original_modality = str(dicom_data.get('Modality', ''))
        original_study_date = str(dicom_data.get('StudyDate', ''))
        original_study_desc = str(dicom_data.get('StudyDescription', ''))
        original_study_time = str(dicom_data.get('StudyTime', ''))

        # Anonymiser les données avec suppression avancée
        anonymized_dicom = anonymize_dicom_advanced(dicom_data)
        
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

        # Sauvegarder les métadonnées (anonymisées)
        metadata_dir = os.path.join(output_base_dir, "metadata")
        os.makedirs(metadata_dir, exist_ok=True)
        metadata_filename = f"metadata_P{patient_counter:03d}_S{study_counter:03d}_SE{series_counter:03d}.json"
        metadata_filepath = os.path.join(metadata_dir, metadata_filename)
        with open(metadata_filepath, 'w') as f:
            json.dump(metadata, f, indent=4)

        # Sauvegarder le fichier .hdr (métadonnées DICOM complètes après anonymisation)
        hdr_dir = os.path.join(output_base_dir, "metadata_hdr")
        os.makedirs(hdr_dir, exist_ok=True)
        hdr_filename = f"metadata_P{patient_counter:03d}_S{study_counter:03d}_SE{series_counter:03d}.hdr"
        hdr_filepath = os.path.join(hdr_dir, hdr_filename)
        with open(hdr_filepath, 'w', encoding='utf-8') as f:
            f.write(conversion_result['hdr_content'])

        # Ajouter l'entrée de nomenclature (avec informations limitées pour respecter l'anonymisation)
        nomenclature_entry = {
            'patient_id_nomenclature': f"P{patient_counter:03d}",
            'study_id_nomenclature': f"S{study_counter:03d}",
            'series_id_nomenclature': f"SE{series_counter:03d}",
            'original_modality': original_modality,
            'Study_Description': original_study_desc if 'StudyDescription' not in metadata_to_remove else "Anonymized"
        }
        nomenclature_entries.append(nomenclature_entry)

        # Incrémenter les compteurs pour le prochain fichier
        patient_counter += 1
        study_counter += 1
        series_counter += 1

        # Supprimer le fichier temporaire
        os.remove(temp_dicom_path)

    # Créer le fichier CSV de nomenclature unique
    csv_dir = os.path.join(output_base_dir, "csv_files")
    os.makedirs(csv_dir, exist_ok=True)
    df = pd.DataFrame(nomenclature_entries)
    csv_filename = os.path.join(csv_dir, "nomenclature_mapping_anonymized.csv")
    df.to_csv(csv_filename, index=False)

    # Créer un fichier de rapport d'anonymisation
    report_content = f"""
    RAPPORT D'ANONYMISATION DES IMAGES MÉDICALES
    ===========================================
    
    Date de traitement: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    Nombre de fichiers traités: {len(files)}
    Métadonnées supprimées par défaut: {len(default_tags_to_remove)} tags
    Métadonnées supplémentaires supprimées: {len(additional_tags_to_remove)} tags
    Total des métadonnées supprimées: {len(all_tags_to_remove)} tags
    
    Métadonnées supplémentaires spécifiées: {metadata_to_remove if metadata_to_remove else "Aucune"}
    
    Fichiers traités:
    {chr(10).join([f"- {file.filename}" for file in files])}
    """
    
    report_dir = os.path.join(output_base_dir, "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_filename = os.path.join(report_dir, "anonymization_report.txt")
    with open(report_filename, 'w', encoding='utf-8') as f:
        f.write(report_content)

    # Créer l'archive ZIP
    zip_path = os.path.join(temp_dir, "processed_medical_images_anonymized")
    shutil.make_archive(zip_path, 'zip', output_base_dir)
    zip_file_path = f"{zip_path}.zip"

    # Lire le fichier ZIP en mémoire
    with open(zip_file_path, "rb") as f:
        zip_data = io.BytesIO(f.read())
    zip_data.seek(0)

    # Fonction de nettoyage des fichiers temporaires
    def cleanup_temp_files():
        shutil.rmtree(temp_dir, ignore_errors=True)

    background_tasks.add_task(cleanup_temp_files)

    # Retourner le fichier ZIP
    return StreamingResponse(
        zip_data,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=medical_images_anonymized.zip"}
    )


@router.get("/sante")
async def verifier_sante():
    """Endpoint de vérification de santé de l'API"""
    return {"statut": "OK", "message": "L'API d'images fonctionne correctement", "timestamp": datetime.now().isoformat()}