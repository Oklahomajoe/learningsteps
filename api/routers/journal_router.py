from typing import AsyncGenerator
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from repositories.postgres_repository import PostgresDB
from services.entry_service import EntryService
from models.entry import Entry, EntryCreate, EntryUpdate


router = APIRouter()

# TODO: Add authentication middleware
# TODO: Add request validation middleware
# TODO: Add rate limiting middleware
# TODO: Add API versioning
# TODO: Add response caching

async def get_entry_service() -> AsyncGenerator[EntryService, None]:
    async with PostgresDB() as db:
        yield EntryService(db)

@router.post("/entries")
async def create_entry(entry_data: EntryCreate, entry_service: EntryService = Depends(get_entry_service)):
    """Create a new journal entry."""
    entry = Entry(**entry_data.model_dump())
    created_entry = await entry_service.create_entry(entry.model_dump())
    return {"detail": "Entry created successfully", "entry": created_entry}

# Implements GET /entries endpoint to list all journal entries
# Example response: [{"id": "123", "work": "...", "struggle": "...", "intention": "..."}]
@router.get("/entries")
async def get_all_entries(entry_service: EntryService = Depends(get_entry_service)):
    """Get all journal entries."""
    result = await entry_service.get_all_entries()
    return {"entries": result, "count": len(result)}

@router.get("/entries/{entry_id}")
async def get_entry(entry_id: UUID, entry_service: EntryService = Depends(get_entry_service)):
    """Return one journal entry, or 404 if it does not exist."""
    entry = await entry_service.get_entry(str(entry_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry

@router.patch("/entries/{entry_id}")
async def update_entry(entry_id: UUID, entry_update: EntryUpdate, entry_service: EntryService = Depends(get_entry_service)):
    """Update a journal entry"""
    result = await entry_service.update_entry(str(entry_id), entry_update.model_dump(exclude_unset=True))
    if not result:
    
        raise HTTPException(status_code=404, detail="Entry not found")
    
    return result

@router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: UUID, entry_service: EntryService = Depends(get_entry_service)):
    """Delete one journal entry, or return 404 if it does not exist."""
    if not await entry_service.delete_entry(str(entry_id)):
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"detail": "Entry deleted successfully", "id": str(entry_id)}

@router.delete("/entries")
async def delete_all_entries(entry_service: EntryService = Depends(get_entry_service)):
    """Delete all journal entries"""
    await entry_service.delete_all_entries()
    return {"detail": "All entries deleted"}
