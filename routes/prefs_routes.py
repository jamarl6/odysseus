"""User preferences API — per-user key/value store backed by a JSON file."""
import json
import os
from typing import Optional
from fastapi import APIRouter, Request
from src.auth_helpers import get_current_user
from src.constants import DATA_DIR
from src.user_paths import get_user_prefs_path
import shutil

LEGACY_PREFS_FILE = os.path.join(DATA_DIR, "user_prefs.json")
BACKUP_PREFS_FILE = os.path.join(DATA_DIR, "user_prefs.legacy_backup.json")

def _migrate_if_needed():
    """Migrate legacy flat or _users format preferences into per-user files."""
    if not os.path.exists(LEGACY_PREFS_FILE):
        return
        
    try:
        with open(LEGACY_PREFS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        if not isinstance(data, dict):
            return
            
        if "_users" in data:
            users_dict = data["_users"]
        else:
            first_user = "admin"
            auth_file = os.path.join(DATA_DIR, "auth.json")
            if os.path.exists(auth_file):
                with open(auth_file, "r", encoding="utf-8") as f:
                    auth_data = json.load(f)
                for u, udata in auth_data.items():
                    if udata.get("is_admin"):
                        first_user = u
                        break
            users_dict = {first_user: data}
            
        for u, prefs in users_dict.items():
            user_path = get_user_prefs_path(u)
            if not os.path.exists(user_path):
                os.makedirs(os.path.dirname(user_path), exist_ok=True)
                with open(user_path, "w", encoding="utf-8") as f:
                    json.dump(prefs, f, indent=2)
                    
        shutil.move(LEGACY_PREFS_FILE, BACKUP_PREFS_FILE)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to migrate legacy prefs: {e}")

def _load_for_user(user: Optional[str] = None) -> dict:
    """Load preferences for a specific user from their isolated folder."""
    _migrate_if_needed()
    if not user:
        user = "default"
        
    path = get_user_prefs_path(user)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_for_user(user: Optional[str], prefs: dict):
    """Save preferences for a specific user to their isolated folder."""
    _migrate_if_needed()
    if not user:
        user = "default"
        
    path = get_user_prefs_path(user)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def setup_prefs_routes():
    router = APIRouter(prefix="/api/prefs", tags=["preferences"])

    @router.get("")
    async def get_all_prefs(request: Request):
        user = get_current_user(request)
        return _load_for_user(user)

    @router.get("/{key}")
    async def get_pref(request: Request, key: str):
        user = get_current_user(request)
        prefs = _load_for_user(user)
        return {"key": key, "value": prefs.get(key)}

    @router.put("/{key}")
    async def set_pref(request: Request, key: str, body: dict):
        user = get_current_user(request)
        prefs = _load_for_user(user)
        prefs[key] = body.get("value")
        _save_for_user(user, prefs)
        return {"key": key, "value": prefs[key]}

    return router
