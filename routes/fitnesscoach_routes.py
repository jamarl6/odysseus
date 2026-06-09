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
                import uuid
                from src.endpoint_resolver import resolve_endpoint
                endpoint_url, model, _ = resolve_endpoint("default", owner=owner)
                
                new_session_id = str(uuid.uuid4())
                sess = session_manager.create_session(
                    session_id=new_session_id,
                    name="[Fitness Coach]",
                    endpoint_url=endpoint_url or "",
                    model=model or "",
                    owner=owner
                )
                
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
