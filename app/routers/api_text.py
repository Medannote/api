from fastapi import FastAPI, File, UploadFile, HTTPException, Form, BackgroundTasks, APIRouter
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

from app.dependencies import *

router = APIRouter()

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

# Endpoints de l'API
@router.get("/")
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

@router.post("/analyser_documents")
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

@router.post("/generer_annotations")
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

@router.post("/telecharger_annotations_zip")
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

@router.post("/supprimer_colonnes_zip")
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
        
        # Read ZIP into memory to avoid file handle leak
        zip_buffer = io.BytesIO()
        with open(zip_path, "rb") as f:
            zip_buffer.write(f.read())
        zip_buffer.seek(0)

        # Nettoyer les fichiers temporaires après envoi
        def remove_temp_files():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        background_tasks.add_task(remove_temp_files)

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=fichiers_modifies.zip"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression des colonnes: {str(e)}")

@router.get("/sante")
async def verifier_sante():
    """Endpoint de vérification de santé de l'API"""
    return {"statut": "OK", "message": "L'API fonctionne correctement", "timestamp": datetime.now().isoformat()}

