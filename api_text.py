from fastapi import FastAPI, File, UploadFile, HTTPException, Form, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
import pandas as pd
from collections import Counter
import docx as python_docx
from docx import Document
import os
import re
import docx
from typing import Dict, List, Optional, Union
import nltk
from datetime import datetime
import json
import io
import zipfile
import tempfile
from pathlib import Path
from pydantic import BaseModel

# Télécharger les stopwords NLTK au démarrage
try:
    from nltk.corpus import stopwords
    nltk.download('stopwords', quiet=True)
except:
    pass

app = FastAPI(
    title="API d'Analyse de Rapports Médicaux",
    description="API pour analyser et traiter des rapports médicaux en français avec support multi-fichiers et export ZIP",
    version="2.0.0"
)

# Modèles Pydantic pour les réponses
class PatientInfo(BaseModel):
    Nom: Optional[str] = None
    Prénom: Optional[str] = None
    Age: Optional[int] = None
    Date: Optional[str] = None
    Symptômes: Optional[str] = None
    Antécédents: Optional[str] = None
    Diagnostic: Optional[str] = None
    Traitement: Optional[str] = None

class ColonnesRequest(BaseModel):
    colonnes_a_supprimer: List[str]

class BatchProcessingResult(BaseModel):
    nombre_fichiers_traites: int
    fichiers_reussis: List[str]
    fichiers_echecs: List[Dict[str, str]]
    donnees_combinees: List[Dict]

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

# Endpoints de l'API
@app.get("/")
async def root():
    """Point d'entrée de l'API"""
    return {
        "message": "API d'Analyse de Rapports Médicaux", 
        "version": "2.0.0",
        "endpoints": {
            "analyser_documents": "POST /analyser_documents - Analyse plusieurs documents médicaux",
            "generer_annotations": "POST /generer_annotations - Génère des annotations pour plusieurs fichiers",
            "telecharger_annotations_zip": "POST /telecharger_annotations_zip - Télécharge les annotations en format ZIP",
            "supprimer_colonnes_zip": "POST /supprimer_colonnes_zip - Supprime des colonnes de plusieurs fichiers et retourne un ZIP"
        }
    }

@app.post("/analyser_documents")
async def analyser_documents(files: List[UploadFile] = File(...)):
    """
    Analyse plusieurs documents médicaux (DOCX ou TXT) et extrait les informations
    """
    try:
        all_data = []
        results = []
        
        for file in files:
            try:
                content = await file.read()
                
                if file.filename.lower().endswith('.docx'):
                    lignes = extract_text_from_docx(content)
                elif file.filename.lower().endswith('.txt'):
                    text_content = content.decode('utf-8')
                    lignes = [line.strip() for line in text_content.split('\n') if line.strip()]
                else:
                    results.append({
                        "filename": file.filename,
                        "status": "error",
                        "error": "Format non supporté. Utilisez .docx ou .txt"
                    })
                    continue
                
                donnees = parse_report(lignes)
                donnees["Fichier_source"] = file.filename
                all_data.append(donnees)
                
                results.append({
                    "filename": file.filename,
                    "status": "success",
                    "donnees_extraites": donnees
                })
                
            except Exception as e:
                results.append({
                    "filename": file.filename,
                    "status": "error",
                    "error": str(e)
                })
        
        df_combined = pd.DataFrame(all_data) if all_data else pd.DataFrame()
        
        return {
            "nombre_fichiers": len(files),
            "resultats": results,
            "donnees_combinees": df_combined.to_dict('records')
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse des documents: {str(e)}")

@app.post("/generer_annotations")
async def generer_annotations(files: List[UploadFile] = File(...)):
    """
    Génère des annotations pour plusieurs fichiers de données médicales
    """
    try:
        all_dfs = []
        results = []
        
        for file in files:
            try:
                content = await file.read()
                filename = file.filename.lower()
                
                # Lire le fichier selon son type
                if filename.endswith('.docx'):
                    lignes = extract_text_from_docx(content)
                    donnees = parse_report(lignes)
                    df = pd.DataFrame([donnees])
                elif filename.endswith('.txt'):
                    text_content = content.decode('utf-8')
                    lignes = [line.strip() for line in text_content.split('\n') if line.strip()]
                    donnees = parse_report(lignes)
                    df = pd.DataFrame([donnees])
                elif filename.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(io.BytesIO(content))
                elif filename.endswith('.csv'):
                    df = pd.read_csv(io.BytesIO(content))
                elif filename.endswith('.json'):
                    df = pd.read_json(io.BytesIO(content))
                else:
                    results.append({
                        "filename": file.filename,
                        "status": "error",
                        "error": "Format non supporté"
                    })
                    continue
                
                # Ajouter le nom du fichier source
                df['Fichier_source'] = file.filename
                all_dfs.append(df)
                
                # Générer les annotations
                df1, df2 = Annotation(df)
                
                results.append({
                    "filename": file.filename,
                    "status": "success",
                    "df_personnel": df1.to_dict('records') if df1 is not None else [],
                    "df_medical": df2.to_dict('records') if df2 is not None else [],
                    "nombre_enregistrements": len(df)
                })
                
            except Exception as e:
                results.append({
                    "filename": file.filename,
                    "status": "error",
                    "error": str(e)
                })
        
        # Combiner tous les DataFrames
        df_combined = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
        df1_combined, df2_combined = Annotation(df_combined)
        
        return {
            "nombre_fichiers": len(files),
            "resultats": results,
            "df_personnel_combine": df1_combined.to_dict('records') if df1_combined is not None else [],
            "df_medical_combine": df2_combined.to_dict('records') if df2_combined is not None else []
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération d'annotations: {str(e)}")

@app.post("/telecharger_annotations_zip")
async def telecharger_annotations_zip(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """
    Génère des annotations pour plusieurs fichiers et retourne un ZIP avec les résultats
    """
    try:
        all_dfs = []
        
        for file in files:
            try:
                content = await file.read()
                filename = file.filename.lower()
                
                # Lire le fichier selon son type
                if filename.endswith('.docx'):
                    lignes = extract_text_from_docx(content)
                    donnees = parse_report(lignes)
                    df = pd.DataFrame([donnees])
                elif filename.endswith('.txt'):
                    text_content = content.decode('utf-8')
                    lignes = [line.strip() for line in text_content.split('\n') if line.strip()]
                    donnees = parse_report(lignes)
                    df = pd.DataFrame([donnees])
                elif filename.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(io.BytesIO(content))
                elif filename.endswith('.csv'):
                    df = pd.read_csv(io.BytesIO(content))
                elif filename.endswith('.json'):
                    df = pd.read_json(io.BytesIO(content))
                else:
                    continue  # Ignorer les formats non supportés
                
                # Ajouter le nom du fichier source
                df['Fichier_source'] = file.filename
                all_dfs.append(df)
                
            except Exception:
                continue  # Ignorer les fichiers avec erreurs
        
        if not all_dfs:
            raise HTTPException(status_code=400, detail="Aucun fichier valide à traiter")
        
        # Combiner tous les DataFrames et générer les annotations
        df_combined = pd.concat(all_dfs, ignore_index=True)
        df1_combined, df2_combined = Annotation(df_combined)
        
        # Créer le ZIP
        zip_content = creer_zip_resultats(df1_combined, df2_combined)
        
        return StreamingResponse(
            io.BytesIO(zip_content),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=annotations_medicales.zip"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du ZIP: {str(e)}")

@app.post("/supprimer_colonnes_zip")
async def supprimer_colonnes_zip(
    background_tasks: BackgroundTasks,
    colonnes_a_supprimer: List[str] = Form(...),
    files: List[UploadFile] = File(...)
):
    """
    Supprime des colonnes de plusieurs fichiers et retourne un ZIP avec les résultats
    """
    try:
        # Créer un répertoire temporaire
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, "fichiers_modifies.zip")
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in files:
                try:
                    content = await file.read()
                    filename = file.filename.lower()
                    
                    # Lire le fichier
                    if filename.endswith(('.xlsx', '.xls')):
                        df = pd.read_excel(io.BytesIO(content))
                    elif filename.endswith('.csv'):
                        df = pd.read_csv(io.BytesIO(content))
                    elif filename.endswith('.json'):
                        df = pd.read_json(io.BytesIO(content))
                    else:
                        continue  # Ignorer les formats non supportés
                    
                    # Supprimer les colonnes spécifiées
                    protected_column = 'ID d\'annotation'
                    cols_to_drop_filtered = [col for col in colonnes_a_supprimer if col != protected_column]
                    existing_cols_to_drop = [col for col in cols_to_drop_filtered if col in df.columns]
                    
                    if existing_cols_to_drop:
                        df_modified = df.drop(columns=existing_cols_to_drop)
                    else:
                        df_modified = df
                    
                    # Ajouter le fichier modifié au ZIP
                    base_name = Path(file.filename).stem
                    extension = Path(file.filename).suffix
                    
                    if extension in ['.xlsx', '.xls']:
                        with io.BytesIO() as buffer:
                            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                                df_modified.to_excel(writer, index=False)
                            zipf.writestr(f"{base_name}_modifie{extension}", buffer.getvalue())
                    else:
                        with io.StringIO() as buffer:
                            df_modified.to_csv(buffer, index=False)
                            zipf.writestr(f"{base_name}_modifie.csv", buffer.getvalue().encode('utf-8'))
                            
                except Exception:
                    continue  # Ignorer les fichiers avec erreurs
        
        # Nettoyer les fichiers temporaires après envoi
        def remove_temp_files():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        background_tasks.add_task(remove_temp_files)
        
        return StreamingResponse(
            open(zip_path, "rb"),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=fichiers_modifies.zip"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression des colonnes: {str(e)}")

@app.get("/sante")
async def verifier_sante():
    """Endpoint de vérification de santé de l'API"""
    return {"statut": "OK", "message": "L'API fonctionne correctement", "timestamp": datetime.now().isoformat()}

