from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Dict, List
from database import get_db, async_session
from models import Message, Task, User, MessageType
from schemas import MessageCreate, MessageResponse
from auth import get_current_user, decode_token
import json

router = APIRouter(prefix="/chat", tags=["Chat"])


# ── WebSocket Connection Manager ──────────────────────────────

class ConnectionManager:
    """Manages WebSocket connections for real-time chat."""

    def __init__(self):
        # task_id -> list of (user_id, websocket)
        self.active_connections: Dict[str, List[tuple]] = {}

    async def connect(self, websocket: WebSocket, task_id: str, user_id: str):
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append((user_id, websocket))

    def disconnect(self, websocket: WebSocket, task_id: str, user_id: str):
        if task_id in self.active_connections:
            self.active_connections[task_id] = [
                (uid, ws) for uid, ws in self.active_connections[task_id]
                if ws != websocket
            ]
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]

    async def send_to_task(self, task_id: str, message: dict, exclude_user: str = None):
        if task_id in self.active_connections:
            for user_id, websocket in self.active_connections[task_id]:
                if user_id != exclude_user:
                    try:
                        await websocket.send_json(message)
                    except Exception:
                        pass


manager = ConnectionManager()


# ── WebSocket Endpoint ─────────────────────────────────────────

@router.websocket("/ws/{task_id}")
async def websocket_chat(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time chat within a task."""
    # Authenticate via query param token
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        return

    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
    except Exception:
        await websocket.close(code=4001)
        return

    await manager.connect(websocket, task_id, user_id)

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            # Save message to database
            async with async_session() as db:
                msg = Message(
                    task_id=task_id,
                    sender_id=user_id,
                    content=message_data.get("content", ""),
                    message_type=MessageType(message_data.get("message_type", "text")),
                )
                db.add(msg)
                await db.commit()

            # Broadcast to other users in the task
            await manager.send_to_task(
                task_id,
                {
                    "type": "message",
                    "sender_id": user_id,
                    "content": message_data.get("content", ""),
                    "message_type": message_data.get("message_type", "text"),
                    "task_id": task_id,
                },
                exclude_user=user_id
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket, task_id, user_id)
    except Exception:
        manager.disconnect(websocket, task_id, user_id)


# ── REST Endpoints for Chat History ────────────────────────────

@router.get("/{task_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get chat history for a task."""
    # Verify user is part of the task
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.requester_id != current_user.id and task.provider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(Message)
        .options(selectinload(Message.sender))
        .where(Message.task_id == task_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()

    responses = []
    for msg in messages:
        resp = MessageResponse.model_validate(msg)
        resp.sender_name = msg.sender.name if msg.sender else None
        responses.append(resp)

    return responses


@router.post("/{task_id}/messages", response_model=MessageResponse, status_code=201)
async def send_message(
    task_id: str,
    data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a message (REST fallback for non-WebSocket clients)."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.requester_id != current_user.id and task.provider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    message = Message(
        task_id=task_id,
        sender_id=current_user.id,
        content=data.content,
        message_type=data.message_type,
    )
    db.add(message)
    await db.flush()

    # Re-query with eager loading to avoid MissingGreenlet in async context
    result = await db.execute(
        select(Message).options(
            selectinload(Message.sender),
        ).where(Message.id == message.id)
    )
    message = result.scalar_one()

    resp = MessageResponse.model_validate(message)
    resp.sender_name = message.sender.name if message.sender else current_user.name

    # Broadcast via WebSocket
    await manager.send_to_task(
        task_id,
        {
            "type": "message",
            "sender_id": str(current_user.id),
            "sender_name": current_user.name,
            "content": data.content,
            "message_type": data.message_type.value,
            "task_id": task_id,
        },
        exclude_user=str(current_user.id)
    )

    return resp
