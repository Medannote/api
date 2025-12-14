"""
Batch Processing Router - Handles ZIP files containing mixed medical data types
"""
from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import os
import tempfile
import zipfile
import shutil
import io
import requests
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# File type mappings
IMAGE_EXTENSIONS = {'.dcm', '.dicom'}
SIGNAL_EXTENSIONS = {'.hea', '.dat', '.qrs', '.edf', '.eeg'}
TEXT_EXTENSIONS = {'.csv', '.xlsx', '.docx', '.txt', '.json'}

# Maximum limits for security
MAX_FILES_IN_ZIP = 1000
MAX_EXTRACTION_SIZE = 500 * 1024 * 1024  # 500MB
MAX_COMPRESSION_RATIO = 100  # Protect against ZIP bombs


def is_safe_path(base_path: str, file_path: str) -> bool:
    """
    Check if file_path is within base_path to prevent path traversal attacks.
    """
    abs_base = os.path.abspath(base_path)
    abs_file = os.path.abspath(file_path)
    return abs_file.startswith(abs_base)


def extract_zip_safely(zip_file: UploadFile, extract_dir: str) -> Tuple[bool, str, List[str]]:
    """
    Safely extract ZIP file with security checks.

    Returns:
        (success, error_message, extracted_files)
    """
    try:
        # Save uploaded ZIP
        zip_path = os.path.join(extract_dir, "upload.zip")
        with open(zip_path, "wb") as f:
            content = zip_file.file.read()
            f.write(content)

        # Check if valid ZIP
        if not zipfile.is_zipfile(zip_path):
            return False, "Le fichier n'est pas un ZIP valide", []

        extracted_files = []
        total_size = 0

        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Check for ZIP bomb
            compressed_size = os.path.getsize(zip_path)
            uncompressed_size = sum(info.file_size for info in zf.infolist())

            if uncompressed_size > MAX_EXTRACTION_SIZE:
                return False, f"Le ZIP est trop volumineux (max {MAX_EXTRACTION_SIZE // (1024*1024)}MB)", []

            if compressed_size > 0 and uncompressed_size / compressed_size > MAX_COMPRESSION_RATIO:
                return False, "ZIP suspect détecté (ratio de compression trop élevé)", []

            # Check file count
            if len(zf.infolist()) > MAX_FILES_IN_ZIP:
                return False, f"Trop de fichiers dans le ZIP (max {MAX_FILES_IN_ZIP})", []

            # Extract files
            for member in zf.infolist():
                # Skip directories
                if member.is_dir():
                    continue

                # Prevent path traversal
                member_path = os.path.join(extract_dir, member.filename)
                if not is_safe_path(extract_dir, member_path):
                    logger.warning(f"Skipping potentially malicious path: {member.filename}")
                    continue

                # Extract file
                zf.extract(member, extract_dir)
                extracted_files.append(member_path)
                total_size += member.file_size

        # Remove the uploaded ZIP file
        os.remove(zip_path)

        return True, "", extracted_files

    except zipfile.BadZipFile:
        return False, "Fichier ZIP corrompu", []
    except Exception as e:
        logger.error(f"Error extracting ZIP: {e}")
        return False, f"Erreur lors de l'extraction: {str(e)}", []


def group_signal_files(files: List[str]) -> List[List[str]]:
    """
    Group signal files by base name (e.g., signal.hea, signal.dat, signal.qrs -> 1 group).
    A signal is composed of up to 3 files with same base name but different extensions.
    """
    signal_groups = {}

    for file_path in files:
        base_name = Path(file_path).stem
        ext = Path(file_path).suffix.lower()

        if base_name not in signal_groups:
            signal_groups[base_name] = []

        signal_groups[base_name].append(file_path)

    # Return as list of groups
    return list(signal_groups.values())


def categorize_files(files: List[str]) -> Dict[str, List]:
    """
    Categorize extracted files by type.

    Returns:
        {
            'images': [file paths],
            'signals': [[group1 files], [group2 files], ...],  # Grouped by 3
            'text': [file paths],
            'unknown': [file paths]
        }
    """
    categorized = {
        'images': [],
        'signals': [],
        'text': [],
        'unknown': []
    }

    for file_path in files:
        ext = Path(file_path).suffix.lower()

        if ext in IMAGE_EXTENSIONS:
            categorized['images'].append(file_path)
        elif ext in SIGNAL_EXTENSIONS:
            categorized['signals'].append(file_path)
        elif ext in TEXT_EXTENSIONS:
            categorized['text'].append(file_path)
        else:
            categorized['unknown'].append(file_path)

    # Group signal files
    if categorized['signals']:
        categorized['signals'] = group_signal_files(categorized['signals'])

    return categorized


async def process_file_category(
    category: str,
    files: List,
    api_base_url: str,
    temp_dir: str
) -> Tuple[bool, bytes, str]:
    """
    Process a category of files and return the result ZIP.

    Returns:
        (success, zip_bytes, error_message)
    """
    try:
        # Use v1 API endpoints for consistency
        endpoint_map = {
            'images': '/api/v1/images/preprocess_dicom_files/',
            'signals': '/api/v1/signaux/upload_signals',
            'text': '/api/v1/text/telecharger_annotations_zip/'
        }

        endpoint = endpoint_map.get(category)
        if not endpoint:
            logger.error(f"Unknown category: {category}")
            return False, b'', f"Catégorie inconnue: {category}"

        url = f"{api_base_url}{endpoint}"
        logger.info(f"Processing {category} at {url}")

        # Prepare files for upload
        upload_files = []

        if category == 'signals':
            # For signals, files is a list of groups
            for group in files:
                for file_path in group:
                    filename = os.path.basename(file_path)
                    with open(file_path, 'rb') as f:
                        upload_files.append(('files', (filename, f.read(), 'application/octet-stream')))
        else:
            # For images and text
            for file_path in files:
                filename = os.path.basename(file_path)
                with open(file_path, 'rb') as f:
                    upload_files.append(('files', (filename, f.read(), 'application/octet-stream')))

        # Send to processing endpoint
        # Timeout needs to be VERY long for DICOM processing (can take 10+ min per file)
        logger.info(f"Sending {len(upload_files)} files to {url}")
        response = requests.post(url, files=upload_files, timeout=3600)  # 60 minutes

        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No error details"
            logger.error(f"Error processing {category}: {response.status_code} - {error_detail}")
            return False, b'', f"Erreur {response.status_code}: {error_detail}"

        # Check if response is ZIP
        if 'application/zip' in response.headers.get('Content-Type', ''):
            return True, response.content, ""
        else:
            return False, b'', f"Réponse inattendue (non-ZIP) pour {category}"

    except Exception as e:
        logger.error(f"Error processing {category}: {e}")
        return False, b'', str(e)


@router.post("/process_zip")
async def process_batch_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Process a ZIP file containing mixed medical data types.

    Accepts: ZIP files containing DICOM images, signal files, and text documents
    Returns: ZIP containing up to 3 sub-ZIPs (one per category)

    Structure of output ZIP:
    - images_results.zip (if DICOM files found)
    - signals_results.zip (if signal files found)
    - text_results.zip (if text files found)
    - processing_report.txt (summary)
    """
    temp_dir = None

    try:
        # Validate file extension
        if not file.filename.lower().endswith('.zip'):
            raise HTTPException(status_code=400, detail="Le fichier doit être un ZIP")

        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)

        logger.info(f"Processing ZIP: {file.filename}")

        # Extract ZIP safely
        success, error_msg, extracted_files = extract_zip_safely(file, extract_dir)

        if not success:
            raise HTTPException(status_code=400, detail=error_msg)

        if not extracted_files:
            raise HTTPException(status_code=400, detail="Aucun fichier trouvé dans le ZIP")

        logger.info(f"Extracted {len(extracted_files)} files")

        # Categorize files
        categorized = categorize_files(extracted_files)

        # Log categorization
        logger.info(f"Categorization: "
                   f"images={len(categorized['images'])}, "
                   f"signals={len(categorized['signals'])} groups, "
                   f"text={len(categorized['text'])}, "
                   f"unknown={len(categorized['unknown'])}")

        # Check if we have processable files
        processable_count = (len(categorized['images']) +
                           len(categorized['signals']) +
                           len(categorized['text']))

        if processable_count == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Aucun fichier traitable trouvé. Fichiers non reconnus: {len(categorized['unknown'])}"
            )

        # Get API base URL from environment or construct from request
        # Use the same host/port that received this request
        api_base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')

        # Process each category
        results = {}
        errors = {}

        for category in ['images', 'signals', 'text']:
            if category == 'signals':
                # Check if we have signal groups
                if not categorized[category]:
                    continue
            else:
                # Check if we have files
                if not categorized[category]:
                    continue

            logger.info(f"Processing {category}...")
            success, zip_content, error = await process_file_category(
                category,
                categorized[category],
                api_base_url,
                temp_dir
            )

            if success:
                results[category] = zip_content
                logger.info(f"{category} processed successfully ({len(zip_content)} bytes)")
            else:
                errors[category] = error
                logger.error(f"Failed to process {category}: {error}")

        # Create final ZIP with all results
        final_zip_buffer = io.BytesIO()

        with zipfile.ZipFile(final_zip_buffer, 'w', zipfile.ZIP_DEFLATED) as final_zip:
            # Add processed ZIPs
            for category, content in results.items():
                zip_name = f"{category}_results.zip"
                final_zip.writestr(zip_name, content)

            # Create processing report
            report_lines = [
                "=" * 60,
                "RAPPORT DE TRAITEMENT PAR LOTS",
                "=" * 60,
                f"\nFichier source: {file.filename}",
                f"Date de traitement: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"\nFichiers extraits: {len(extracted_files)}",
                f"\n--- CATÉGORISATION ---",
                f"Images DICOM: {len(categorized['images'])} fichiers",
                f"Signaux: {len(categorized['signals'])} groupes",
                f"Documents texte: {len(categorized['text'])} fichiers",
                f"Non reconnus: {len(categorized['unknown'])} fichiers",
                f"\n--- RÉSULTATS ---",
            ]

            for category in ['images', 'signals', 'text']:
                if category in results:
                    report_lines.append(f"✓ {category}: Traité avec succès")
                elif category in errors:
                    report_lines.append(f"✗ {category}: Erreur - {errors[category]}")
                else:
                    report_lines.append(f"- {category}: Aucun fichier à traiter")

            if categorized['unknown']:
                report_lines.append(f"\n--- FICHIERS NON RECONNUS ---")
                for unknown_file in categorized['unknown'][:20]:  # Limit to 20
                    report_lines.append(f"  - {os.path.basename(unknown_file)}")
                if len(categorized['unknown']) > 20:
                    report_lines.append(f"  ... et {len(categorized['unknown']) - 20} autres")

            report_lines.append(f"\n{'=' * 60}")
            report_lines.append("Traitement terminé.")
            report_lines.append("=" * 60)

            report_content = "\n".join(report_lines)
            final_zip.writestr("processing_report.txt", report_content.encode('utf-8'))

        final_zip_buffer.seek(0)

        # Schedule cleanup
        def remove_temp_files():
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

        background_tasks.add_task(remove_temp_files)

        # Return final ZIP
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"processed_batch_{timestamp}.zip"

        return StreamingResponse(
            final_zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch processing error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Erreur lors du traitement du fichier ZIP."
        )
    finally:
        # Always cleanup temp directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup temp directory: {cleanup_error}")


@router.get("/")
async def batch_info():
    """Information about the batch processing endpoint"""
    return {
        "message": "Batch Processing API",
        "version": "1.0.0",
        "endpoint": "/batch/process_zip",
        "description": "Process ZIP files containing mixed medical data types",
        "supported_types": {
            "images": list(IMAGE_EXTENSIONS),
            "signals": list(SIGNAL_EXTENSIONS),
            "text": list(TEXT_EXTENSIONS)
        },
        "limits": {
            "max_files": MAX_FILES_IN_ZIP,
            "max_size_mb": MAX_EXTRACTION_SIZE // (1024 * 1024),
            "max_compression_ratio": MAX_COMPRESSION_RATIO
        }
    }
