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

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import io

app = FastAPI()

# Fonctions de prétraitement du notebook (adaptées pour l'API)

def anonymize_dicom(dicom_data: pydicom.dataset.FileDataset) -> pydicom.dataset.FileDataset:
    """Anonymise les données sensibles du fichier DICOM."""
    tags_to_remove = [
        (0x0010, 0x0010), (0x0010, 0x0020), (0x0010, 0x0030), (0x0010, 0x0040),
        (0x0010, 0x1000), (0x0010, 0x1001), (0x0010, 0x2160), (0x0008, 0x0020),
        (0x0008, 0x0030), (0x0008, 0x0090), (0x0008, 0x1050), (0x0008, 0x1080)
    ]
    anonymized_dicom = dicom_data.copy()
    for tag in tags_to_remove:
        if tag in anonymized_dicom:
            del anonymized_dicom[tag]
    anonymized_dicom.InstitutionName = "Anonymized Healthcare Facility"
    return anonymized_dicom

def convert_dicom_to_nifti(dicom_data: pydicom.dataset.FileDataset, patient_id: str, study_id: str, series_id: str):
    """Convertit un fichier DICOM en format NIfTI et extrait les métadonnées."""
    try:
        pixel_array = dicom_data.pixel_array
        nifti_img = nib.Nifti1Image(pixel_array, np.eye(4))

        metadata = {
            'patient_id': patient_id,
            'study_id': study_id,
            'series_id': series_id,
            'original_sop_instance_uid': str(dicom_data.get('SOPInstanceUID', 'Unknown')),
            'image_dimensions': pixel_array.shape,
            'pixel_spacing': [float(i) for i in dicom_data.get('PixelSpacing', [1.0, 1.0])],
            'modality': str(dicom_data.get('Modality', 'Unknown')),
            'conversion_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return {'metadata': metadata, 'nifti_img': nifti_img, 'pixel_array': pixel_array}
    except Exception as e:
        print(f"Erreur lors de la conversion en NIfTI : {e}")
        return None

def resize_image(image_array: np.ndarray, target_size=(256, 256)) -> np.ndarray:
    """Redimensionne l'image à la taille cible."""
    if len(image_array.shape) > 2:
        resized_slices = []
        for i in range(image_array.shape[0]):
            img = Image.fromarray(image_array[i].astype(np.float32))
            img = img.resize(target_size, Image.Resampling.LANCZOS)
            resized_slices.append(np.array(img))
        return np.stack(resized_slices, axis=0)
    else:
        img = Image.fromarray(image_array.astype(np.float32))
        img = img.resize(target_size, Image.Resampling.LANCZOS)
        return np.array(img)

def normalize_image(image_array: np.ndarray) -> np.ndarray:
    """Normalise les valeurs de pixel de l'image entre 0 et 1."""
    min_val = np.min(image_array)
    max_val = np.max(image_array)
    if max_val - min_val > 0:
        normalized_image = (image_array - min_val) / (max_val - min_val)
    else:
        normalized_image = image_array.astype(np.float32)
    return normalized_image

def apply_histogram_equalization(image_array: np.ndarray) -> np.ndarray:
    """Applique l'égalisation d'histogramme à l'image."""
    if len(image_array.shape) > 2:
        equalized_slices = []
        for i in range(image_array.shape[0]):
            equalized_slices.append(exposure.equalize_hist(image_array[i]))
        return np.stack(equalized_slices, axis=0)
    else:
        return exposure.equalize_hist(image_array)

@app.post("/preprocess_dicom_files/")
async def preprocess_dicom_files(files: List[UploadFile] = File(...)):
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
            resized_image = resize_image(image_data, target_size=(256, 256))
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