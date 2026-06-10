import os
import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from src.auth_helpers import effective_user

router = APIRouter()

def get_fitness_metrics_path(request: Request) -> str:
    user = effective_user(request) or "default"
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

@router.post("/api/fitness_coach/dashboard")
async def update_dashboard(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    path = get_fitness_metrics_path(request)
    workspace = os.path.dirname(path)
    
    # Load existing or default
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = get_default_metrics()
    else:
        data = get_default_metrics()

    # Update fields dynamically
    for key, val in payload.items():
        if isinstance(val, dict) and key in data and isinstance(data[key], dict):
            data[key].update(val)
        else:
            data[key] = val

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        # Append all new values to messwerte_log.md for history so the AI can read them
        from datetime import datetime
        log_path = os.path.join(workspace, "messwerte_log.md")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # We only log if there is any data
        if payload:
            log_entry = f"\n### Messwerte vom {now_str}\n```json\n{json.dumps(payload, indent=2)}\n```\n"
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
                
        return JSONResponse(content={"status": "success", "data": data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class NotePayload(BaseModel):
    note: str

@router.post("/api/fitness_coach/note")
async def add_temporary_note(request: Request, payload: NotePayload):
    path = get_fitness_metrics_path(request)
    workspace = os.path.dirname(path)
    notes_path = os.path.join(workspace, "temporaere_notizen.md")
    
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d")
    
    try:
        with open(notes_path, "a", encoding="utf-8") as f:
            f.write(f"- {now_str}: {payload.note}\n")
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
