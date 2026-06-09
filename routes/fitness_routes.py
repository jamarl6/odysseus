import os
import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from src.auth_helpers import get_current_user

router = APIRouter()

def get_fitness_metrics_path(request: Request) -> str:
    user = get_current_user(request) or "default"
    # Same base path logic as chat_routes.py
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    workspace = os.path.join(base_dir, "data", "users", user, "fitness_data")
    os.makedirs(workspace, exist_ok=True)
    return os.path.join(workspace, "fitness_metrics.json")

def get_default_metrics():
    return {
        "recovery": {
            "score": "-",
            "trend": "neutral",
            "text": "Waiting for Apple Watch Data"
        },
        "condition": {
            "score": "-",
            "trend": "neutral",
            "text": "Waiting for Apple Watch Data"
        },
        "movement": {
            "current": 0,
            "goal": 0,
            "unit": "kcal",
            "text": "Waiting for Apple Watch Data"
        }
    }

@router.get("/api/fitness_coach/dashboard")
async def get_dashboard(request: Request):
    path = get_fitness_metrics_path(request)
    if not os.path.exists(path):
        # Return default if not exists
        return JSONResponse(content=get_default_metrics())
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content=get_default_metrics())

class MetricsPayload(BaseModel):
    recovery: dict = None
    condition: dict = None
    movement: dict = None

@router.post("/api/fitness_coach/dashboard")
async def update_dashboard(request: Request, payload: MetricsPayload):
    path = get_fitness_metrics_path(request)
    
    # Load existing or default
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = get_default_metrics()
    else:
        data = get_default_metrics()

    # Update fields
    if payload.recovery is not None:
        data["recovery"].update(payload.recovery)
    if payload.condition is not None:
        data["condition"].update(payload.condition)
    if payload.movement is not None:
        data["movement"].update(payload.movement)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return JSONResponse(content={"status": "success", "data": data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
