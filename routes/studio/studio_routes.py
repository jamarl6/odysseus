import os
import uuid
import time
import httpx
import logging
import base64
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from core.database import SessionLocal, StudioMedia
from src.auth_helpers import get_current_user, require_privilege
from src.constants import STUDIO_MEDIA_DIR, UPLOAD_DIR
from src.settings import load_settings, get_user_setting
from routes.studio.studio_helpers import _owner_filter, _media_to_dict, get_openrouter_api_key
import mimetypes

os.makedirs(STUDIO_MEDIA_DIR, exist_ok=True)
router = APIRouter()
logger = logging.getLogger(__name__)

class PhotoGenRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = None
    model: Optional[str] = None
    aspect_ratio: Optional[str] = "16:9"
    base_media_id: Optional[str] = None

class VideoGenRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = None
    model: Optional[str] = None
    base_media_id: Optional[str] = None

def _get_base64_data_url(file_id: str) -> str:
    path = os.path.join(UPLOAD_DIR, file_id)
    if not os.path.isfile(path):
        for root, dirs, files in os.walk(UPLOAD_DIR):
            if file_id in files:
                path = os.path.join(root, file_id)
                break
    if not os.path.isfile(path):
        raise HTTPException(404, "Base media file not found")
        
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        b64_str = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64_str}"

@router.get("/api/studio/models")
async def get_studio_models():
    """Returns a curated list of top OpenRouter models for image and video generation."""
    return {
        "photo": [
            {"id": "black-forest-labs/flux-1.1-pro-ultra", "name": "Flux 1.1 Pro Ultra"},
            {"id": "black-forest-labs/flux-1.1-pro", "name": "Flux 1.1 Pro"},
            {"id": "google/imagen-3", "name": "Google Imagen 3"},
            {"id": "openai/dall-e-3", "name": "DALL-E 3"},
            {"id": "stabilityai/stable-diffusion-3.5-large", "name": "Stable Diffusion 3.5 Large"}
        ],
        "video": [
            {"id": "luma/dream-machine", "name": "Luma Dream Machine"},
            {"id": "runwayml/gen-3-alpha", "name": "Runway Gen-3 Alpha"},
            {"id": "kling-ai/kling-v1", "name": "Kling AI v1"},
            {"id": "minimax/video-01", "name": "MiniMax Video-01"},
            {"id": "haiper/haiper-2", "name": "Haiper 2.0"}
        ]
    }

@router.get("/api/studio/library")
async def studio_library(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(24, ge=1, le=100),
) -> Dict[str, Any]:
    user = get_current_user(request)
    db = SessionLocal()
    try:
        q = db.query(StudioMedia).filter(StudioMedia.is_active == True)
        q = _owner_filter(q, user)
        total = q.count()
        rows = q.order_by(StudioMedia.created_at.desc()).offset(offset).limit(limit).all()
        return {
            "media": [_media_to_dict(m) for m in rows],
            "total": total,
            "offset": offset,
            "limit": limit
        }
    finally:
        db.close()

@router.get("/api/studio/media/{filename}")
async def get_studio_media(request: Request, filename: str):
    user = get_current_user(request)
    db = SessionLocal()
    try:
        m = db.query(StudioMedia).filter(StudioMedia.filename == filename).first()
        if not m or (m.owner and m.owner != user):
            raise HTTPException(404, "Media not found")
        
        path = os.path.join(STUDIO_MEDIA_DIR, filename)
        if not os.path.exists(path):
            raise HTTPException(404, "File not found on disk")
        return FileResponse(path)
    finally:
        db.close()

@router.delete("/api/studio/{media_id}")
async def delete_studio_media(request: Request, media_id: str):
    user = require_privilege(request, "can_generate_images")
    db = SessionLocal()
    try:
        m = db.query(StudioMedia).filter(StudioMedia.id == media_id).first()
        if not m or (m.owner and m.owner != user):
            raise HTTPException(404, "Media not found")
        m.is_active = False
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()

@router.post("/api/studio/generate/photo")
async def generate_photo(request: Request, req: PhotoGenRequest):
    user = require_privilege(request, "can_generate_images")
    db = SessionLocal()
    try:
        api_key = get_openrouter_api_key(db)
        if not api_key:
            raise HTTPException(400, "OpenRouter API key not configured. Add OpenRouter in Settings -> Models.")
        
        settings = load_settings()
        target_model = req.model or get_user_setting("studio_openrouter_photo_model", user, settings.get("studio_openrouter_photo_model", ""))
        if not target_model:
            raise HTTPException(400, "No photo model specified. Set a default in Settings -> Studio or pass a model.")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/pewdiepie-archdaemon/odysseus",
            "X-OpenRouter-Title": "Odysseus Studio"
        }
        
        payload = {
            "model": target_model,
            "prompt": req.prompt,
            "response_format": {"type": "b64_json"}
        }
        if req.negative_prompt:
            payload["negative_prompt"] = req.negative_prompt
        
        if req.base_media_id:
            payload["input_references"] = [{"url": _get_base64_data_url(req.base_media_id)}]

        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post("https://openrouter.ai/api/v1/images/generations", json=payload, headers=headers)
            if resp.status_code != 200:
                raise HTTPException(500, f"OpenRouter API error: {resp.text}")
            
            data = resp.json()
            b64_data = data.get("data", [{}])[0].get("b64_json")
            url_data = data.get("data", [{}])[0].get("url")
            
            if not b64_data and not url_data:
                raise HTTPException(500, "No image data returned from OpenRouter.")
            
            media_id = f"st_{uuid.uuid4().hex[:12]}"
            filename = f"{media_id}.png"
            filepath = os.path.join(STUDIO_MEDIA_DIR, filename)
            
            if b64_data:
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(b64_data))
            else:
                img_resp = await client.get(url_data)
                with open(filepath, "wb") as f:
                    f.write(img_resp.content)

            new_media = StudioMedia(
                id=media_id,
                filename=filename,
                media_type="photo",
                prompt=req.prompt,
                model=target_model,
                owner=user,
                file_size=os.path.getsize(filepath)
            )
            db.add(new_media)
            db.commit()
            
            return _media_to_dict(new_media)
    except Exception as e:
        logger.exception("Photo generation failed")
        raise HTTPException(500, str(e))
    finally:
        db.close()

@router.post("/api/studio/generate/video")
async def generate_video(request: Request, req: VideoGenRequest):
    user = require_privilege(request, "can_generate_images")
    db = SessionLocal()
    try:
        api_key = get_openrouter_api_key(db)
        if not api_key:
            raise HTTPException(400, "OpenRouter API key not configured. Add OpenRouter in Settings -> Models.")
        
        settings = load_settings()
        target_model = req.model or get_user_setting("studio_openrouter_video_model", user, settings.get("studio_openrouter_video_model", ""))
        if not target_model:
            raise HTTPException(400, "No video model specified. Set a default in Settings -> Studio or pass a model.")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/pewdiepie-archdaemon/odysseus",
            "X-OpenRouter-Title": "Odysseus Studio"
        }
        
        payload = {
            "model": target_model,
            "prompt": req.prompt
        }
        if req.negative_prompt:
            payload["negative_prompt"] = req.negative_prompt
        
        if req.base_media_id:
            payload["input_references"] = [{"url": _get_base64_data_url(req.base_media_id)}]

        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post("https://openrouter.ai/api/v1/videos/generations", json=payload, headers=headers)
            # OpenRouter typically returns job/polling info
            if resp.status_code != 200:
                raise HTTPException(500, f"OpenRouter API error: {resp.text}")
            
            data = resp.json()
            # If it returns synchronous result (unlikely but possible)
            url_data = data.get("data", [{}])[0].get("url")
            polling_url = data.get("polling_url")
            job_id = data.get("id")

            media_id = f"stv_{uuid.uuid4().hex[:12]}"
            filename = f"{media_id}.mp4"
            
            new_media = StudioMedia(
                id=media_id,
                filename=filename,
                media_type="video",
                prompt=req.prompt,
                model=target_model,
                owner=user,
                job_id=polling_url or job_id, # store polling url as job id for simplicity
                job_status="pending" if polling_url else "completed"
            )
            
            if url_data:
                # Sync completion
                filepath = os.path.join(STUDIO_MEDIA_DIR, filename)
                vid_resp = await client.get(url_data)
                with open(filepath, "wb") as f:
                    f.write(vid_resp.content)
                new_media.file_size = os.path.getsize(filepath)
            
            db.add(new_media)
            db.commit()
            return _media_to_dict(new_media)
    except Exception as e:
        logger.exception("Video generation failed")
        raise HTTPException(500, str(e))
    finally:
        db.close()

@router.get("/api/studio/jobs/{media_id}")
async def check_video_job(request: Request, media_id: str):
    user = require_privilege(request, "can_generate_images")
    db = SessionLocal()
    try:
        m = db.query(StudioMedia).filter(StudioMedia.id == media_id).first()
        if not m or (m.owner and m.owner != user):
            raise HTTPException(404, "Media not found")
        
        if m.job_status == "completed":
            return _media_to_dict(m)
            
        api_key = get_openrouter_api_key(db)
        headers = {"Authorization": f"Bearer {api_key}"}
        
        async with httpx.AsyncClient(timeout=60) as client:
            # We stored the full polling URL in job_id
            resp = await client.get(m.job_id, headers=headers)
            if resp.status_code != 200:
                raise HTTPException(500, "Polling failed")
                
            data = resp.json()
            status = data.get("status")
            
            if status == "completed" or "url" in data.get("data", [{}])[0]:
                url_data = data.get("data", [{}])[0].get("url")
                if url_data:
                    filepath = os.path.join(STUDIO_MEDIA_DIR, m.filename)
                    vid_resp = await client.get(url_data)
                    with open(filepath, "wb") as f:
                        f.write(vid_resp.content)
                    m.file_size = os.path.getsize(filepath)
                    m.job_status = "completed"
                    db.commit()
            elif status == "failed":
                m.job_status = "failed"
                db.commit()
                
            return _media_to_dict(m)
    finally:
        db.close()
