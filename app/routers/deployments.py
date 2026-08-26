import os
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from app.schemas import DeploymentRequest, DeploymentResponse
from app.services.packages import InvalidDeployment, PACKAGES, UnknownModel, generate_package

router = APIRouter(tags=["deployments"])

@router.post("/deployments", response_model=DeploymentResponse)
def deployments(payload: DeploymentRequest, request: Request) -> DeploymentResponse:
    try:
        base_url = os.getenv("PUBLIC_BASE_URL") or str(request.base_url).rstrip("/")
        return generate_package(payload, base_url.rstrip("/"))
    except InvalidDeployment as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except UnknownModel as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

@router.get("/deployments/{deployment_id}/download")
def download(deployment_id: str) -> Response:
    package = PACKAGES.get(deployment_id)
    if package is None or package.expires_at <= datetime.now(timezone.utc):
        PACKAGES.pop(deployment_id, None)
        raise HTTPException(status_code=404, detail="Deployment package not found or expired")
    return Response(package.content, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{package.filename}"'})
