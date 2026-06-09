"""Fitness Coach routes — initialize the Coach session and manage data directory."""

import os
from fastapi import APIRouter, Request, HTTPException
from core.database import SessionLocal, Session as DBSession, ChatMessage as DBChatMessage
from src.auth_helpers import get_current_user
from src.config import config

def setup_fitnesscoach_routes(session_manager) -> APIRouter:
    router = APIRouter(prefix="/api/fitnesscoach", tags=["fitnesscoach"])

    @router.get("/session")
    async def get_coach_session(request: Request):
        """Resolve or create the pinned Fitness Coach session for this user."""
        owner = get_current_user(request) or ""
        
        # Ensure the user's fitness data directory exists
        user_path = owner if owner else "default"
        coach_dir = config.data.data_dir / "users" / user_path / "fitness_data"
        os.makedirs(coach_dir, exist_ok=True)

        db = SessionLocal()
        try:
            # Look for the pinned coach session
            # We use a special name tag or a dedicated metadata column. Since we only have 'name', we can use a reserved name.
            coach_session = db.query(DBSession).filter(
                DBSession.owner == owner,
                DBSession.name == "[Fitness Coach]"
            ).first()

            if not coach_session:
                # Create it
                from src.llm_core import llm_call_async
                # Just create a fresh session via session_manager
                new_session_id = session_manager.create_session()
                sess = session_manager.get_session(new_session_id)
                sess.name = "[Fitness Coach]"
                sess.owner = owner
                
                # Update DB
                db_sess = db.query(DBSession).filter(DBSession.id == new_session_id).first()
                if db_sess:
                    db_sess.name = "[Fitness Coach]"
                    db_sess.owner = owner
                    db.commit()
                
                coach_session_id = new_session_id
            else:
                coach_session_id = coach_session.id

            return {
                "session_id": coach_session_id,
                "workspace": str(coach_dir.absolute())
            }
        finally:
            db.close()

    return router
