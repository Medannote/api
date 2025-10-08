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
from typing import List, Dict, Optional, Union
from PIL import Image
import wfdb
import glob
import uuid
import tempfile
import zipfile
import io
from pathlib import Path
from collections import Counter
import docx as python_docx
from docx import Document
import re
import nltk
from pydantic import BaseModel
import matplotlib.pyplot as plt
import logging

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, BackgroundTasks, APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration constants
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB per file
MAX_FILES = 50  # Maximum number of files per request
ALLOWED_DICOM_EXTENSIONS = {'.dcm', '.dicom'}
ALLOWED_SIGNAL_EXTENSIONS = {'.hea', '.dat'}
ALLOWED_TEXT_EXTENSIONS = {'.docx', '.txt', '.xlsx', '.xls', '.csv', '.json'}

# Validation functions
async def validate_file_upload(files: List[UploadFile], max_files: int = MAX_FILES, max_size: int = MAX_FILE_SIZE, allowed_extensions: set = None):
    """
    Validate uploaded files for size, count, and extension.

    Args:
        files: List of uploaded files
        max_files: Maximum number of files allowed
        max_size: Maximum size per file in bytes
        allowed_extensions: Set of allowed file extensions (with dot, e.g., {'.dcm', '.txt'})

    Raises:
        HTTPException: If validation fails
    """
    if not files:
        raise HTTPException(status_code=400, detail="Aucun fichier n'a été téléchargé.")

    if len(files) > max_files:
        raise HTTPException(
            status_code=400,
            detail=f"Trop de fichiers. Maximum autorisé : {max_files}, reçu : {len(files)}"
        )

    for file in files:
        # Check file size by reading content
        content = await file.read()
        await file.seek(0)  # Reset file pointer

        if len(content) > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"Fichier '{file.filename}' trop volumineux. Taille maximale : {max_size / (1024*1024):.1f}MB"
            )

        # Check file extension if specified
        if allowed_extensions:
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Extension de fichier non autorisée : '{file_ext}'. Extensions autorisées : {', '.join(allowed_extensions)}"
                )

# Télécharger les stopwords NLTK au démarrage
try:
    from nltk.corpus import stopwords
    nltk.download('stopwords', quiet=True)
except:
    pass


from fastapi import FastAPI, UploadFile, File, HTTPException, APIRouter
from fastapi.responses import StreamingResponse
import io

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
    """Convertit un fichier DICOM en format NIfTI et extrait les métadonnées, y compris un .hdr."""
    try:
        pixel_array = dicom_data.pixel_array
        nifti_img = nib.Nifti1Image(pixel_array, np.eye(4))

        # Métadonnées principales
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

        # Extraction de toutes les métadonnées DICOM (hors pixel data)
        dicom_metadata = {}
        for elem in dicom_data:
            if elem.tag != (0x7fe0, 0x0010):  # Pixel Data
                try:
                    dicom_metadata[elem.name] = str(elem.value)
                except Exception:
                    pass

        # Génération du contenu .hdr (ici en JSON pour la lisibilité)
        hdr_content = json.dumps(dicom_metadata, indent=2, ensure_ascii=False)

        return {
            'metadata': metadata,
            'nifti_img': nifti_img,
            'pixel_array': pixel_array,
            'hdr_content': hdr_content  # À sauvegarder comme .hdr si besoin
        }
    except Exception as e:
        print(f"Erreur lors de la conversion en NIfTI : {e}")
        logger.error(f"Erreur lors de la conversion en NIfTI : {e}")
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


# Fonctions de traitement des signaux (adaptées de votre code)
def afficher_toutes_metadonnées(signal_path: str) -> Dict:
    """Affiche toutes les métadonnées disponibles d'un signal médical."""
    try:
        record = wfdb.rdheader(signal_path)
        return record.__dict__
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la lecture des métadonnées : {e}")

def stocker_csv(folder_path: str) -> pd.DataFrame:
    """
    Extrait les métadonnées de tous les signaux WFDB d'un dossier
    et les renvoie sous forme d'un DataFrame pandas.
    """
    all_metadata = []
    
    # Parcourt tous les fichiers .hea dans le dossier
    hea_files = glob.glob(os.path.join(folder_path, '*.hea'))
    
    if not hea_files:
        raise HTTPException(status_code=404, detail=f"Aucun fichier .hea trouvé dans le dossier : {folder_path}")
    
    for file_path in hea_files:
        signal_name = os.path.basename(file_path).replace('.hea', '')
        
        try:
            record = wfdb.rdheader(os.path.join(folder_path, signal_name))
            
            metadata_dict = {'signal_name': signal_name}
            for key, value in record.__dict__.items():
                if key.startswith('_') or key in ['e_p_signal', 'e_p_sig_name']:
                    continue
                
                if isinstance(value, (list, tuple)):
                    value = str(value)
                
                metadata_dict[key] = value
            
            all_metadata.append(metadata_dict)
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur lors du traitement du signal '{signal_name}' : {e}")
    
    return pd.DataFrame(all_metadata)

def plot_signal(signal_path: str) -> io.BytesIO:
    """Lit et trace le graphique du signal, retourne l'image en mémoire."""
    try:
        record = wfdb.rdrecord(signal_path)
        
        # Créer le plot en mémoire
        buffer = io.BytesIO()
        plt.figure(figsize=(12, 6))
        wfdb.plot_wfdb(record=record, title=f"Signal médical : {record.record_name}")
        plt.savefig(buffer, format='png')
        plt.close()
        buffer.seek(0)
        
        return buffer
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du traçage du signal : {e}")

def division_df(folder_path: str) -> tuple:

    """
    Charge les métadonnées, génère un ID unique pour chaque enregistrement,
    et divise le DataFrame en deux : informations personnelles et métadonnées médicales.
    """
    df = stocker_csv(folder_path)
    
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="Aucune donnée chargée")
    
    # Générer un ID unique entier formaté sur 8 chiffres pour chaque enregistrement
    df['id'] = [f'{i:08d}' for i in range(1, len(df) + 1)]
    
    # Définir les colonnes pour les informations personnelles
    personal_info_cols = ['signal_name', 'id']
    for col in ['nom', 'prenom', 'age', 'patient_name']:
        if col in df.columns:
            personal_info_cols.append(col)
    
    # Créer le DataFrame des informations personnelles
    personal_info_df = df[personal_info_cols].copy()
    
    # Créer le DataFrame des métadonnées avec les colonnes restantes
    metadata_cols = [col for col in df.columns if col not in ['nom', 'prenom', 'age', 'patient_name']]
    metadata_df = df[metadata_cols].copy()
    
    return personal_info_df, metadata_df

# Fonctions d'extraction et de traitement
def extract_text_from_docx(file_content: bytes) -> List[str]:
    """Extraction du texte d'un fichier Word depuis les bytes"""
    doc = python_docx.Document(io.BytesIO(file_content))
    return [p.text for p in doc.paragraphs if p.text.strip() != ""]

def clean_text(text: str) -> str:
    """
    Nettoie le texte en:
    1. Convertissant en minuscules
    2. Supprimant la ponctuation et les chiffres
    3. Supprimant les stopwords français et médicaux
    4. Supprimant les mots trop courts (<3 caractères)
    """
    # Liste étendue de stopwords médicaux
    medical_stopwords = {
        'patient', 'docteur', 'médecin', 'consultation', 'examen',
        'antecedent', 'antecedents', 'histoire', 'cas',
        'motif', 'depuis', 'jours', 'jour', 'mois', 'annee', 'années',
        'presente', 'presentant', 'sans', 'avec', 'pendant', 'apres', 'avant', 
        'traitement', 'douleur', 'douleurs'
    }
    
    # Conversion en minuscules
    text = text.lower()
    
    # Suppression des chiffres et ponctuation spécifique
    text = re.sub(r'\d+', '', text)
    text = re.sub(r'[^\w\s]|_', ' ', text)
    
    # Suppression des stopwords (français + médicaux)
    try:
        stop_words = set(stopwords.words('french')).union(medical_stopwords)
    except:
        stop_words = medical_stopwords
    
    words = text.split()
    # Filtrage des mots trop courts et stopwords
    words = [word for word in words if word not in stop_words and len(word) > 2]
    
    return " ".join(words)

def parse_report1(lines: List[str]) -> Dict:
    """Analyse les lignes de texte pour repérer les champs importants (format 1)"""
    report = {}
    lines_as_string = '\n'.join(lines)
    
    # Extraction des informations du patient
    patient_match = re.search(r'Patient:\s*([^,]+),\s*(\d+)\s*ans', lines_as_string, re.IGNORECASE)
    if patient_match:
        full_name = patient_match.group(1).split()
        if len(full_name) > 1:
            report["Nom"] = full_name[-1]  # Le dernier mot comme nom
            report["Prénom"] = ' '.join(full_name[:-1])  # Le reste comme prénom
        else:
            report["Prénom"] = full_name[0] if full_name else ""
        report["Age"] = int(patient_match.group(2))
    
    # Extraction de la date
    date_match = re.search(r'Date:\s*(.+)', lines_as_string, re.IGNORECASE)
    if date_match:
        report["Date"] = date_match.group(1).strip()
    
    # Extraction des autres champs
    for line in lines:
        lower_line = line.lower()
        if "motif" in lower_line and "consultation" in lower_line and ":" in line:
            report["Symptômes"] = clean_text(line.split(":", 1)[1])
        elif "antécédents" in lower_line and ":" in line:
            report["Antécédents"] = clean_text(line.split(":", 1)[1])
        elif "diagnostic" in lower_line and ":" in line:
            report["Diagnostic"] = clean_text(line.split(":", 1)[1])
        elif "traitement" in lower_line and ":" in line:
            report["Traitement"] = clean_text(line.split(":", 1)[1])
    
    return report

def parse_report2(lines: List[str]) -> Dict:
    """Fonction alternative pour extraire les informations (format 2)"""
    report = {}
    lines_as_string = '\n'.join(lines)
    
    # Extraction du nom
    nom_match = re.search(r'Nom:\s*([^\n]+)', lines_as_string, re.IGNORECASE)
    if nom_match:
        report["Nom"] = nom_match.group(1).strip()
    else:
        for line in lines:
            if 'nom' in line.lower() and ':' in line:
                report["Nom"] = line.split(':', 1)[1].strip()
                break
    
    # Extraction du prénom
    prenom_match = re.search(r'Prénom:\s*([^\n]+)', lines_as_string, re.IGNORECASE)
    if prenom_match:
        report["Prénom"] = prenom_match.group(1).strip()
    else:
        for line in lines:
            if 'prénom' in line.lower() and ':' in line:
                report["Prénom"] = line.split(':', 1)[1].strip()
                break
            elif 'prenom' in line.lower() and ':' in line:
                report["Prénom"] = line.split(':', 1)[1].strip()
                break
    
    # Extraction de l'âge
    age_match = re.search(r'Âge:\s*(\d+)', lines_as_string, re.IGNORECASE)
    if age_match:
        report["Age"] = int(age_match.group(1))
    else:
        for line in lines:
            if 'âge' in line.lower() and ':' in line:
                age_str = line.split(':', 1)[1].strip()
                age_num = re.search(r'\d+', age_str)
                if age_num:
                    report["Age"] = int(age_num.group())
                    break
            elif 'age' in line.lower() and ':' in line:
                age_str = line.split(':', 1)[1].strip()
                age_num = re.search(r'\d+', age_str)
                if age_num:
                    report["Age"] = int(age_num.group())
                    break
    
    # Extraction de la date
    date_match = re.search(r'Date:\s*([^\n]+)', lines_as_string, re.IGNORECASE)
    if date_match:
        report["Date"] = date_match.group(1).strip()
    else:
        for line in lines:
            if 'date' in line.lower() and ':' in line:
                report["Date"] = line.split(':', 1)[1].strip()
                break
    
    # Extraction des autres champs avec regex
    motif_match = re.search(r'Motif de consultation:\s*([^\n]+)', lines_as_string, re.IGNORECASE)
    if motif_match:
        report["Symptômes"] = clean_text(motif_match.group(1))
    else:
        for line in lines:
            if 'motif' in line.lower() and ':' in line:
                report["Symptômes"] = clean_text(line.split(':', 1)[1])
                break
    
    # Antécédents
    antecedents_match = re.search(r'Antécédents médicaux:\s*([^\n]+)', lines_as_string, re.IGNORECASE)
    if antecedents_match:
        report["Antécédents"] = clean_text(antecedents_match.group(1))
    else:
        for line in lines:
            if 'antécédents' in line.lower() and ':' in line:
                report["Antécédents"] = clean_text(line.split(':', 1)[1])
                break
    
    # Diagnostic
    diagnostic_match = re.search(r'Diagnostic:\s*([^\n]+)', lines_as_string, re.IGNORECASE)
    if diagnostic_match:
        report["Diagnostic"] = clean_text(diagnostic_match.group(1))
    else:
        for line in lines:
            if 'diagnostic' in line.lower() and ':' in line:
                report["Diagnostic"] = clean_text(line.split(':', 1)[1])
                break
    
    # Traitement
    traitement_match = re.search(r'Traitement:\s*([^\n]+)', lines_as_string, re.IGNORECASE)
    if traitement_match:
        report["Traitement"] = clean_text(traitement_match.group(1))
    else:
        for line in lines:
            if 'traitement' in line.lower() and ':' in line:
                report["Traitement"] = clean_text(line.split(':', 1)[1])
                break
    
    return report

def parse_report(lines: List[str]) -> Dict:
    """Analyse les lignes pour déterminer le format et appelle la fonction appropriée"""
    lines_as_string = '\n'.join(lines)
    
    # Vérifier le format "Patient: Nom, Âge ans"
    patient_match = re.search(r'Patient:\s*([^,]+),\s*(\d+)\s*ans', lines_as_string, re.IGNORECASE)
    if patient_match:
        return parse_report1(lines)
    else:
        return parse_report2(lines)

def generate_annotation_id(row: pd.Series) -> int:
    """Génère un ID d'annotation de 11 chiffres"""
    date_str = row.get('Date', datetime.now().strftime("%d %B %Y"))
    
    try:
        try:
            current_date = datetime.strptime(str(date_str), '%d %B %Y')
        except ValueError:
            try:
                current_date = datetime.strptime(str(date_str), '%Y-%m-%d')
            except ValueError:
                try:
                    current_date = datetime.strptime(str(date_str), '%d/%m/%Y')
                except ValueError:
                    current_date = datetime.now()
    except:
        current_date = datetime.now()
    
    aa = str(current_date.year % 100).zfill(2)
    mm = str(current_date.month).zfill(2)
    jj = str(current_date.day).zfill(2)
    
    sexe = 1  # Par défaut féminin
    if 'Sexe' in row and pd.notna(row['Sexe']):
        sexe_str = str(row['Sexe']).lower()
        sexe = 0 if any(m in sexe_str for m in ['homme', 'male', 'm', 'h']) else 1
    
    age_str = '000'
    if 'Age' in row and pd.notna(row['Age']):
        try:
            age_str = str(int(row['Age'])).zfill(3)
        except ValueError:
            age_str = '000'
    
    diagnostic = 1
    if 'Diagnostic' in row and pd.notna(row['Diagnostic']):
        diag_str = str(row['Diagnostic']).lower()
        if any(n in diag_str for n in ['aucun', 'normal', 'rien à signaler', 'sans particularité']):
            diagnostic = 0
    
    annotation_id_str = f"{aa}{mm}{jj}{sexe}{age_str}{diagnostic}"
    
    if len(annotation_id_str) == 11:
        return int(annotation_id_str)
    else:
        return 0

def Annotation(df: pd.DataFrame) -> tuple:
    """Génère l'ID d'annotation et divise en deux DataFrames"""
    if df is None or df.empty:
        return None, None
    
    # S'assurer que la colonne Age existe et est numérique
    if 'Age' in df.columns:
        df['Age'] = pd.to_numeric(df['Age'], errors='coerce').fillna(0).astype(int)
    else:
        df['Age'] = 0
    
    df['ID d\'annotation'] = df.apply(generate_annotation_id, axis=1)
    df['Année de naissance'] = datetime.now().year - df['Age']
    
    colonnes_df1 = ['Nom', 'Prénom', 'Année de naissance', 'ID d\'annotation']
    # Garder seulement les colonnes qui existent
    colonnes_df1 = [col for col in colonnes_df1 if col in df.columns]
    
    df1 = df[colonnes_df1] if colonnes_df1 else pd.DataFrame()
    
    colonnes_df2 = [col for col in df.columns if col not in ['Nom', 'Prénom', 'Année de naissance', 'Age']]
    df2 = df[colonnes_df2] if colonnes_df2 else pd.DataFrame()
    
    return df1, df2

def creer_zip_resultats(df_personnel: pd.DataFrame, df_medical: pd.DataFrame) -> bytes:
    """
    Crée un fichier ZIP contenant les résultats en différents formats
    """
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Ajouter CSV
        if not df_personnel.empty:
            csv_personnel = io.StringIO()
            df_personnel.to_csv(csv_personnel, index=False, encoding='utf-8')
            zip_file.writestr('donnees_personnelles.csv', csv_personnel.getvalue().encode('utf-8'))
        
        if not df_medical.empty:
            csv_medical = io.StringIO()
            df_medical.to_csv(csv_medical, index=False, encoding='utf-8')
            zip_file.writestr('donnees_medicales.csv', csv_medical.getvalue().encode('utf-8'))
        
        # Ajouter Excel
        if not df_personnel.empty:
            excel_personnel = io.BytesIO()
            with pd.ExcelWriter(excel_personnel, engine='openpyxl') as writer:
                df_personnel.to_excel(writer, index=False, sheet_name='Personnel')
            zip_file.writestr('donnees_personnelles.xlsx', excel_personnel.getvalue())
        
        if not df_medical.empty:
            excel_medical = io.BytesIO()
            with pd.ExcelWriter(excel_medical, engine='openpyxl') as writer:
                df_medical.to_excel(writer, index=False, sheet_name='Medical')
            zip_file.writestr('donnees_medicales.xlsx', excel_medical.getvalue())
        
        # Ajouter JSON
        if not df_personnel.empty:
            json_personnel = df_personnel.to_json(orient='records', indent=2, force_ascii=False)
            zip_file.writestr('donnees_personnelles.json', json_personnel.encode('utf-8'))
        
        if not df_medical.empty:
            json_medical = df_medical.to_json(orient='records', indent=2, force_ascii=False)
            zip_file.writestr('donnees_medicales.json', json_medical.encode('utf-8'))
        
        # Ajouter un fichier README
        readme_content = """# Résultats d'analyse de rapports médicaux

## Fichiers inclus:
- donnees_personnelles.csv/xlsx/json : Informations d'identification des patients
- donnees_medicales.csv/xlsx/json : Données médicales anonymisées avec ID d'annotation

## Structure des données:

### Données personnelles:
- Nom, Prénom, Année de naissance, ID d'annotation

### Données médicales:
- ID d'annotation, Date, Symptômes, Antécédents, Diagnostic, Traitement

## Note:
L'ID d'annotation permet de relier les données personnelles aux données médicales tout en maintenant l'anonymisation.
"""
        zip_file.writestr('README.md', readme_content.encode('utf-8'))
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()
