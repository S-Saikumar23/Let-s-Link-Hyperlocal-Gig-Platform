import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from database import get_db
from models import TaskMedia, Task, User
from auth import get_current_user
from config import settings

router = APIRouter(prefix="/uploads", tags=["Uploads"])


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov"}


def validate_file(file: UploadFile) -> str:
    """Validate file extension and size. Returns the extension."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    return ext


@router.post("/task-media/{task_id}")
async def upload_task_media(
    task_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload an image or video for a task."""
    from sqlalchemy import select

    # Verify task exists and user owns it
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Validate file
    ext = validate_file(file)

    # Read file content and check size
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE // (1024*1024)}MB"
        )

    # Create upload directory
    upload_dir = os.path.join(settings.UPLOAD_DIR, "tasks", task_id)
    os.makedirs(upload_dir, exist_ok=True)

    # Save file
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    # Determine media type
    media_type = "video" if ext in {".mp4", ".mov"} else "image"

    # Save record to database
    url = f"/uploads/tasks/{task_id}/{filename}"
    media = TaskMedia(
        task_id=task_id,
        url=url,
        media_type=media_type,
    )
    db.add(media)
    await db.flush()
    await db.refresh(media)

    return {
        "id": str(media.id),
        "url": url,
        "media_type": media_type,
        "filename": filename,
    }


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a profile avatar."""
    ext = validate_file(file)

    if ext in {".mp4", ".mov"}:
        raise HTTPException(status_code=400, detail="Avatar must be an image, not a video")

    content = await file.read()
    if len(content) > 2 * 1024 * 1024:  # 2MB limit for avatars
        raise HTTPException(status_code=400, detail="Avatar too large. Maximum size: 2MB")

    # Create upload directory
    upload_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
    os.makedirs(upload_dir, exist_ok=True)

    # Delete old avatar file if exists
    if current_user.avatar_url and current_user.avatar_url.startswith("/uploads/avatars/"):
        old_path = current_user.avatar_url.lstrip("/")
        if os.path.exists(old_path):
            os.remove(old_path)

    # Save file
    filename = f"{current_user.id}{ext}"
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    # Update user record
    url = f"/uploads/avatars/{filename}"
    current_user.avatar_url = url
    await db.flush()

    return {"url": url, "message": "Avatar updated successfully"}
