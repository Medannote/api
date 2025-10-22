import os
import pydicom
import nibabel as nib
import numpy as np
import pandas as pd
from skimage.transform import resize
from skimage import exposure
import shutil
import json
import base64
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


@router.post("/convert_dicom_for_viewer")
async def convert_dicom_for_viewer(file: UploadFile = File(...)):
    """
    Convert DICOM file to viewable format with metadata for the data viewer.
    Returns JSON with image data and metadata instead of ZIP.
    """
    try:
        # Read DICOM file
        content = await file.read()
        dicom_dataset = pydicom.dcmread(io.BytesIO(content))

        # Extract pixel data
        pixel_array = dicom_dataset.pixel_array

        # Normalize to 8-bit for display
        if pixel_array.max() > 255:
            pixel_array = ((pixel_array - pixel_array.min()) /
                          (pixel_array.max() - pixel_array.min()) * 255).astype(np.uint8)
        else:
            pixel_array = pixel_array.astype(np.uint8)

        # Convert to PIL Image
        if len(pixel_array.shape) == 2:
            # Grayscale
            image = Image.fromarray(pixel_array, mode='L')
        else:
            # RGB
            image = Image.fromarray(pixel_array, mode='RGB')

        # Convert to base64 PNG
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        image_data_url = f"data:image/png;base64,{image_base64}"

        # Extract metadata
        metadata = {
            'patient_name': str(getattr(dicom_dataset, 'PatientName', 'Unknown')),
            'patient_id': str(getattr(dicom_dataset, 'PatientID', 'Unknown')),
            'patient_birth_date': str(getattr(dicom_dataset, 'PatientBirthDate', 'Unknown')),
            'patient_sex': str(getattr(dicom_dataset, 'PatientSex', 'Unknown')),
            'modality': str(getattr(dicom_dataset, 'Modality', 'Unknown')),
            'body_part': str(getattr(dicom_dataset, 'BodyPartExamined', 'Unknown')),
            'study_date': str(getattr(dicom_dataset, 'StudyDate', 'Unknown')),
            'study_time': str(getattr(dicom_dataset, 'StudyTime', 'Unknown')),
            'study_description': str(getattr(dicom_dataset, 'StudyDescription', 'Unknown')),
            'series_description': str(getattr(dicom_dataset, 'SeriesDescription', 'Unknown')),
            'institution': str(getattr(dicom_dataset, 'InstitutionName', 'Unknown')),
            'manufacturer': str(getattr(dicom_dataset, 'Manufacturer', 'Unknown')),
            'rows': int(getattr(dicom_dataset, 'Rows', 0)),
            'columns': int(getattr(dicom_dataset, 'Columns', 0)),
            'pixel_spacing': str(getattr(dicom_dataset, 'PixelSpacing', 'Unknown')),
            'slice_thickness': str(getattr(dicom_dataset, 'SliceThickness', 'Unknown')),
        }

        return {
            'success': True,
            'image_data': image_data_url,
            'metadata': metadata,
            'original_filename': file.filename
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error converting DICOM: {str(e)}"
        )