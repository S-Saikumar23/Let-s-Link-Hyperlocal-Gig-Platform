"""
Task proof routes — before/after photo evidence for task completion.
"""
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import TaskProof, Task, User
from auth import get_current_user

router = APIRouter(prefix="/tasks", tags=["Task Proofs"])

PROOF_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads", "proofs")
os.makedirs(PROOF_DIR, exist_ok=True)


@router.post("/{task_id}/proof")
async def upload_task_proof(
    task_id: str,
    proof_type: str = Form(...),
    caption: str = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload before/after/delivery proof photo for a task."""
    valid_types = {"before", "after", "delivery", "completion"}
    if proof_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"proof_type must be one of: {valid_types}")

    # Verify task exists and user is participant
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.id not in (task.requester_id, task.provider_id):
        raise HTTPException(status_code=403, detail="Only task participants can upload proof")

    # Validate file
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WebP images allowed")

    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    # Save file
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"{task_id[:8]}_{proof_type}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(PROOF_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(contents)

    file_url = f"/uploads/proofs/{filename}"

    proof = TaskProof(
        task_id=task_id,
        uploaded_by=current_user.id,
        proof_type=proof_type,
        file_url=file_url,
        caption=caption,
    )
    db.add(proof)
    await db.flush()

    return {
        "id": str(proof.id),
        "proof_type": proof_type,
        "file_url": file_url,
        "message": f"{proof_type.title()} proof uploaded successfully!",
    }


@router.get("/{task_id}/proofs")
async def get_task_proofs(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all proof photos for a task."""
    result = await db.execute(
        select(TaskProof)
        .where(TaskProof.task_id == task_id)
        .order_by(TaskProof.created_at.asc())
    )
    proofs = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "proof_type": p.proof_type,
            "file_url": p.file_url,
            "caption": p.caption,
            "uploaded_by": str(p.uploaded_by),
            "created_at": p.created_at.isoformat(),
        }
        for p in proofs
    ]
