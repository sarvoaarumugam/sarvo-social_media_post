"""Asset endpoints — the fixed background and preset thumbnail designs that live
in the assets/ folder, so the UI can show them before anything is generated."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.exceptions.handlers import AppError
from app.services.image.service import list_preset_thumbnails, preset_path

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("")
async def list_assets():
    settings = get_settings()
    return {
        "background": Path(settings.background_image_file).exists(),
        "thumbnails": list_preset_thumbnails(),
    }


@router.get("/background/file")
async def get_background_file():
    settings = get_settings()
    p = Path(settings.background_image_file)
    if not p.exists():
        raise AppError("No fixed background in assets/.", status_code=404)
    return FileResponse(p, media_type="image/png")


@router.get("/thumbnail/{name}/file")
async def get_preset_thumbnail_file(name: str):
    try:
        return FileResponse(preset_path(name), media_type="image/png")
    except FileNotFoundError:
        raise AppError("Unknown preset thumbnail.", status_code=404)
