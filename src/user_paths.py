import os
from src.constants import DATA_DIR

def get_user_dir(user: str) -> str:
    """Get the base directory for a specific user."""
    safe_user = user.strip() if user and user.strip() else "default"
    path = os.path.join(DATA_DIR, "users", safe_user)
    os.makedirs(path, exist_ok=True)
    return path

def get_user_prefs_path(user: str) -> str:
    """Get the preferences file path for a user."""
    return os.path.join(get_user_dir(user), "user_prefs.json")

def get_user_personal_docs_path(user: str) -> str:
    """Get the personal documents directory for a user."""
    path = os.path.join(get_user_dir(user), "personal_docs")
    os.makedirs(path, exist_ok=True)
    return path
