import asyncio
import sys
sys.path.insert(0, '.')
from database import async_session
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from models import Task, User, TaskOffer, TaskStatus
from schemas import TaskResponse

async def main():
    async with async_session() as session:
        # Reproduce the exact list_tasks query
        query = select(Task).options(
            selectinload(Task.requester),
            selectinload(Task.category)
        ).where(Task.status == TaskStatus.OPEN).order_by(Task.created_at.desc()).limit(20).offset(0)
        
        result = await session.execute(query)
        tasks = result.scalars().all()
        print(f"Found {len(tasks)} open tasks")
        
        # Try to serialize like the endpoint does
        task_responses = []
        for task in tasks:
            print(f"\nProcessing task: {task.title}")
            try:
                resp = TaskResponse.model_validate(task)
                print(f"  ✓ Serialized successfully")
                
                # Try counting offers
                offer_count = await session.execute(
                    select(func.count(TaskOffer.id)).where(TaskOffer.task_id == task.id)
                )
                resp.offers_count = offer_count.scalar() or 0
                print(f"  ✓ Offers count: {resp.offers_count}")
                
                task_responses.append(resp)
            except Exception as e:
                print(f"  ✗ ERROR: {type(e).__name__}: {e}")
        
        print(f"\nTotal responses: {len(task_responses)}")
        
        # Print full JSON output for one task
        if task_responses:
            import json
            print("\nSample task JSON:")
            print(json.dumps(task_responses[0].model_dump(mode='json'), indent=2, default=str))

asyncio.run(main())
