import os
from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.agent.knowledge_manager import KnowledgeManager
from shibaclaw.webui.agent_manager import agent_manager

def _get_km() -> KnowledgeManager:
    if not agent_manager.config:
        agent_manager.load_latest_config()
    if not agent_manager.config:
        raise RuntimeError("No config loaded")
    return KnowledgeManager(agent_manager.config.workspace_path)

async def api_knowledge_list(request: Request):
    try:
        km = _get_km()
        collections = km.list_collections()
        return JSONResponse({"collections": collections})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

async def api_knowledge_create(request: Request):
    data = await request.json()
    col_id = data.get("id")
    name = data.get("name")
    description = data.get("description", "")
    
    if not col_id or not name:
        return JSONResponse({"error": "id and name are required"}, status_code=422)
        
    km = _get_km()
    try:
        col = km.create_collection(col_id, name, description)
        return JSONResponse(col, status_code=201)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

async def api_knowledge_delete(request: Request):
    collection_id = request.path_params["collection_id"]
    try:
        km = _get_km()
        km.delete_collection(collection_id)
        return JSONResponse({"status": "deleted"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

async def api_knowledge_upload(request: Request):
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
        
        content = await file_item.read()
        with open(temp_path, "wb") as buffer:
            buffer.write(content)
            
        km.add_document(collection_id, temp_path, file_item.filename)
        return JSONResponse({"status": "uploaded", "filename": file_item.filename})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        if 'temp_path' in locals() and temp_path.exists():
            try:
                os.remove(temp_path)
            except Exception:
                pass
