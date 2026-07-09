import os
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from shibaclaw.agent.knowledge_manager import KnowledgeManager
from shibaclaw.webui.agent_manager import agent_manager

def _get_km() -> KnowledgeManager:
    if not agent_manager.config:
        agent_manager.load_latest_config()
    if not agent_manager.config:
        raise RuntimeError("No config loaded")
    return KnowledgeManager(agent_manager.config.workspace_path)

async def api_knowledge_list(request: Request):
    """List all available knowledge base collections."""
    try:
        km = _get_km()
        collections = await run_in_threadpool(km.list_collections)
        return JSONResponse({"collections": collections})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_knowledge_create(request: Request):
    """Create a new knowledge base collection."""
    data = await request.json()
    col_id = data.get("id")
    name = data.get("name")
    description = data.get("description", "")
    
    if not col_id or not name:
        return JSONResponse({"error": "id and name are required"}, status_code=422)
        
    km = _get_km()
    try:
        col = await run_in_threadpool(km.create_collection, col_id, name, description)
        return JSONResponse(col, status_code=201)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_knowledge_update(request: Request):
    """Update an existing knowledge base collection (e.g. rename)."""
    collection_id = request.path_params["collection_id"]
    try:
        data = await request.json()
        name = data.get("name")
        description = data.get("description")
        km = _get_km()
        meta = await run_in_threadpool(km.update_collection, collection_id, name, description)
        return JSONResponse(meta)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_knowledge_delete(request: Request):
    """Delete an existing knowledge base collection."""
    collection_id = request.path_params["collection_id"]
    try:
        km = _get_km()
        await run_in_threadpool(km.delete_collection, collection_id)
        return JSONResponse({"status": "deleted"})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_knowledge_upload(request: Request):
    """Upload a file to a specific knowledge base collection."""
    collection_id = request.path_params["collection_id"]
    form = await request.form()
    file_item = form.get("file")
    if not file_item:
        return JSONResponse({"error": "no file provided"}, status_code=400)
        
    try:
        km = _get_km()
        temp_dir = km.workspace_path / "scratch" / "uploads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / file_item.filename
        
        with open(temp_path, "wb") as buffer:
            while chunk := await file_item.read(8192):
                buffer.write(chunk)
            
        await run_in_threadpool(km.add_document, collection_id, temp_path, file_item.filename)
        return JSONResponse({"status": "uploaded", "filename": file_item.filename})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if 'temp_path' in locals() and temp_path.exists():
            try:
                os.remove(temp_path)
            except Exception:
                pass
