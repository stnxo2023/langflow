import hashlib
from datetime import datetime, timezone
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from langflow.api.v1.schemas import UploadFileResponse
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.flow import Flow
from langflow.services.deps import get_session, get_storage_service
from langflow.services.storage.service import StorageService
from langflow.services.storage.utils import build_content_type_from_extension

router = APIRouter(tags=["Files"], prefix="/files")


# Create dep that gets the flow_id from the request
# then finds it in the database and returns it while
# using the current user as the owner
def get_flow_id(
    flow_id: UUID,
    current_user=Depends(get_current_active_user),
    session=Depends(get_session),
):
    flow_id_str = str(flow_id)
    # AttributeError: 'SelectOfScalar' object has no attribute 'first'
    flow = session.get(Flow, flow_id_str)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    if flow.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't have access to this flow")
    return flow_id_str


@router.post("/upload/{flow_id}", status_code=HTTPStatus.CREATED)
async def upload_file(
    file: UploadFile,
    flow_id: Annotated[UUID, Depends(get_flow_id)],
    current_user=Depends(get_current_active_user),
    session=Depends(get_session),
    storage_service: StorageService = Depends(get_storage_service),
):
    try:
        max_file_size_upload = get_storage_service().settings_service.settings.max_file_size_upload
        if file.size > max_file_size_upload * 1024 * 1024:
            raise HTTPException(
                status_code=413, detail=f"File size is larger than the maximum file size {max_file_size_upload}MB."
            )

        flow_id_str = str(flow_id)
        flow = session.get(Flow, flow_id_str)
        if flow.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You don't have access to this flow")

        file_content = await file.read()
        timestamp = datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = file.filename or hashlib.sha256(file_content).hexdigest()
        full_file_name = f"{timestamp}_{file_name}"
        folder = flow_id_str
        await storage_service.save_file(flow_id=folder, file_name=full_file_name, data=file_content)
        return UploadFileResponse(flowId=flow_id_str, file_path=f"{folder}/{full_file_name}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/download/{flow_id}/{file_name}")
async def download_file(
    file_name: str, flow_id: UUID, storage_service: Annotated[StorageService, Depends(get_storage_service)]
):
    try:
        flow_id_str = str(flow_id)
        extension = file_name.split(".")[-1]

        if not extension:
            raise HTTPException(status_code=500, detail=f"Extension not found for file {file_name}")

        content_type = build_content_type_from_extension(extension)

        if not content_type:
            raise HTTPException(status_code=500, detail=f"Content type not found for extension {extension}")

        file_content = await storage_service.get_file(flow_id=flow_id_str, file_name=file_name)
        headers = {
            "Content-Disposition": f"attachment; filename={file_name} filename*=UTF-8''{file_name}",
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(file_content)),
        }
        return StreamingResponse(BytesIO(file_content), media_type=content_type, headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/images/{flow_id}/{file_name}")
async def download_image(
    file_name: str, flow_id: UUID, storage_service: Annotated[StorageService, Depends(get_storage_service)]
):
    try:
        extension = file_name.split(".")[-1]
        flow_id_str = str(flow_id)

        if not extension:
            raise HTTPException(status_code=500, detail=f"Extension not found for file {file_name}")

        content_type = build_content_type_from_extension(extension)

        if not content_type:
            raise HTTPException(status_code=500, detail=f"Content type not found for extension {extension}")
        if not content_type.startswith("image"):
            raise HTTPException(status_code=500, detail=f"Content type {content_type} is not an image")

        file_content = await storage_service.get_file(flow_id=flow_id_str, file_name=file_name)
        return StreamingResponse(BytesIO(file_content), media_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/profile_pictures/{folder_name}/{file_name}")
async def download_profile_picture(
    folder_name: str,
    file_name: str,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    try:
        extension = file_name.split(".")[-1]
        config_dir = get_storage_service().settings_service.settings.config_dir
        config_path = Path(config_dir)  # type: ignore[arg-type]
        folder_path = config_path / "profile_pictures" / folder_name
        content_type = build_content_type_from_extension(extension)
        file_content = await storage_service.get_file(flow_id=folder_path, file_name=file_name)  # type: ignore[arg-type]
        return StreamingResponse(BytesIO(file_content), media_type=content_type)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/profile_pictures/list")
async def list_profile_pictures(storage_service: Annotated[StorageService, Depends(get_storage_service)]):
    try:
        config_dir = get_storage_service().settings_service.settings.config_dir
        config_path = Path(config_dir)  # type: ignore[arg-type]

        people_path = config_path / "profile_pictures/People"
        space_path = config_path / "profile_pictures/Space"

        people = await storage_service.list_files(flow_id=people_path)  # type: ignore[arg-type]
        space = await storage_service.list_files(flow_id=space_path)  # type: ignore[arg-type]

        files = [f"People/{i}" for i in people]
        files += [f"Space/{i}" for i in space]

        return {"files": files}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/list/{flow_id}")
async def list_files(
    flow_id: Annotated[UUID, Depends(get_flow_id)],
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    try:
        flow_id_str = str(flow_id)
        files = await storage_service.list_files(flow_id=flow_id_str)
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/delete/{flow_id}/{file_name}")
async def delete_file(
    file_name: str,
    flow_id: Annotated[UUID, Depends(get_flow_id)],
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    try:
        flow_id_str = str(flow_id)
        await storage_service.delete_file(flow_id=flow_id_str, file_name=file_name)
        return {"message": f"File {file_name} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
