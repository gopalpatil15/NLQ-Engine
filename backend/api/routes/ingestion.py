from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Request
import os
import uuid
import tempfile
from typing import List
import logging
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class DatabaseRequest(BaseModel):
    connection_string: str


@router.post("/database")
async def connect_database(request: Request, connection_string: str = None):
    """Connect to database and discover schema.

    Accepts connection_string as a query parameter (?connection_string=...) or in JSON body {"connection_string": "..."}.
    """
    schema_discovery = request.app.state.schema_discovery

    # Prefer query param; otherwise try to parse JSON body
    conn = connection_string
    if not conn:
        try:
            body = await request.json()
            if isinstance(body, dict):
                conn = body.get('connection_string')
        except Exception:
            conn = None

    if not conn:
        raise HTTPException(status_code=400, detail='Missing connection_string')

    try:
        schema = schema_discovery.analyze_database(conn)
        return {
            'status': 'success',
            'message': 'Schema discovered successfully',
            'schema': schema
        }
    except Exception as e:
        logger.exception('Database connection failed')
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/database")
async def connect_database_get(request: Request, connection_string: str = None):
    """GET wrapper for connect_database to make testing easier (accepts query param)."""
    return await connect_database(request, connection_string)


@router.post("/documents")
async def upload_documents(
    request: Request,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """Upload and process multiple documents"""
    document_processor = request.app.state.document_processor
    processing_status = request.app.state.processing_status

    try:
        saved_paths = []
        for file in files:
            # Validate file type
            allowed_extensions = [".pdf", ".docx", ".txt", ".csv"]
            file_extension = os.path.splitext(file.filename)[1].lower()
            if file_extension not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file_extension}"
                )

            # Save file temporarily
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{file.filename}")
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            saved_paths.append(file_path)

        # Create processing job
        job_id = str(uuid.uuid4())
        processing_status[job_id] = {
            "status": "processing",
            "total_files": len(saved_paths),
            "processed_files": 0,
            "message": "Starting document processing"
        }

        # Background processing
        background_tasks.add_task(
            process_documents_background,
            request.app,
            job_id,
            saved_paths
        )

        return {
            "status": "accepted",
            "job_id": job_id,
            "message": f"Processing {len(saved_paths)} documents in background"
        }

    except Exception as e:
        logger.exception("Document upload failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{job_id}")
async def get_ingestion_status(job_id: str, request: Request):
    """Check ingestion progress"""
    processing_status = request.app.state.processing_status
    if job_id not in processing_status:
        raise HTTPException(status_code=404, detail="Job not found")

    return processing_status[job_id]


def process_documents_background(app, job_id: str, file_paths: List[str]):
    """Background task for document processing"""
    document_processor = app.state.document_processor
    processing_status = app.state.processing_status
    try:
        processing_status[job_id]["message"] = "Extracting text from documents"

        # Process documents
        result = document_processor.process_documents(file_paths)

        # Update status
        processing_status[job_id].update({
            "status": "completed",
            "processed_files": len(result.get("processed", [])),
            "failed_files": len(result.get("failed", [])),
            "result": result,
            "message": f"Processed {len(result.get('processed', []))} documents successfully"
        })

    except Exception as e:
        logger.exception("Background processing failed")
        processing_status[job_id].update({
            "status": "failed",
            "message": str(e)
        })

    finally:
        # Clean up temp files
        for file_path in file_paths:
            try:
                os.remove(file_path)
            except OSError:
                pass
        
