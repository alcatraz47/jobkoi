"""API routes for document generation and artifact retrieval."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.document import (
    DocumentArtifactListResponse,
    DocumentArtifactResponse,
    DocumentGenerateRequest,
    DocumentGenerateResponse,
)
from app.services.document_service import (
    DocumentArtifactNotFoundError,
    DocumentDependencyNotFoundError,
    DocumentFileMissingError,
    DocumentService,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/cv", response_model=DocumentGenerateResponse, status_code=status.HTTP_201_CREATED)
def generate_cv(
    request: DocumentGenerateRequest,
    session: Session = Depends(get_db_session),
) -> DocumentGenerateResponse:
    """Generate CV document artifacts from a tailored snapshot.

    Args:
        request: Document generation request payload.
        session: Database session dependency.

    Returns:
        Generated document response.

    Raises:
        HTTPException: If source snapshot dependencies are missing.
    """

    service = DocumentService(session)
    try:
        return service.generate_cv(request)
    except DocumentDependencyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/cover-letter", response_model=DocumentGenerateResponse, status_code=status.HTTP_201_CREATED)
def generate_cover_letter(
    request: DocumentGenerateRequest,
    session: Session = Depends(get_db_session),
) -> DocumentGenerateResponse:
    """Generate cover letter artifacts from a tailored snapshot.

    Args:
        request: Document generation request payload.
        session: Database session dependency.

    Returns:
        Generated document response.

    Raises:
        HTTPException: If source snapshot dependencies are missing.
    """

    service = DocumentService(session)
    try:
        return service.generate_cover_letter(request)
    except DocumentDependencyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/snapshots/{snapshot_id}", response_model=DocumentArtifactListResponse)
def list_snapshot_documents(
    snapshot_id: str,
    session: Session = Depends(get_db_session),
) -> DocumentArtifactListResponse:
    """List document artifacts generated for one snapshot.

    Args:
        snapshot_id: Snapshot identifier.
        session: Database session dependency.

    Returns:
        Document artifact list response.

    Raises:
        HTTPException: If snapshot is missing.
    """

    service = DocumentService(session)
    try:
        return service.list_snapshot_artifacts(snapshot_id)
    except DocumentDependencyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{artifact_id}", response_model=DocumentArtifactResponse)
def get_document_artifact(
    artifact_id: str,
    session: Session = Depends(get_db_session),
) -> DocumentArtifactResponse:
    """Get persisted metadata for one generated artifact.

    Args:
        artifact_id: Artifact identifier.
        session: Database session dependency.

    Returns:
        Artifact metadata response.

    Raises:
        HTTPException: If artifact does not exist.
    """

    service = DocumentService(session)
    try:
        return service.get_artifact(artifact_id)
    except DocumentArtifactNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{artifact_id}/download")
def download_document_artifact(
    artifact_id: str,
    session: Session = Depends(get_db_session),
) -> FileResponse:
    """Download generated document artifact content.

    Args:
        artifact_id: Artifact identifier.
        session: Database session dependency.

    Returns:
        FastAPI file download response.

    Raises:
        HTTPException: If artifact metadata or file content is missing.
    """

    service = DocumentService(session)
    try:
        file_path, mime_type, file_name = service.get_artifact_file(artifact_id)
    except DocumentArtifactNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentFileMissingError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return FileResponse(path=file_path, media_type=mime_type, filename=file_name)
