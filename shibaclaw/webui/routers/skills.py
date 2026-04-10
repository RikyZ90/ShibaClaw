"""Skills management API endpoints."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from loguru import logger

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.agent.skills import SkillsLoader


def _get_loader() -> SkillsLoader:
    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config
    workspace = cfg.workspace_path if cfg else None
    if not workspace:
        raise ValueError("No workspace configured")
    return SkillsLoader(workspace)


async def api_skills_list(request: Request):
    """List all skills with metadata, availability, and pinned status."""
    try:
        loader = _get_loader()
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    cfg = agent_manager.config
    pinned = cfg.agents.defaults.pinned_skills if cfg else []
    max_pinned = cfg.agents.defaults.max_pinned_skills if cfg else 5

    skills = []
    for s in loader.list_skills(filter_unavailable=False):
        meta = loader.get_skill_metadata(s["name"]) or {}
        skill_meta = loader._parse_shibaclaw_metadata(meta.get("metadata", ""))
        available = loader._check_requirements(skill_meta)
        missing = loader._get_missing_requirements(skill_meta) if not available else ""
        always_yaml = bool(skill_meta.get("always") or meta.get("always"))

        skills.append({
            "name": s["name"],
            "description": meta.get("description", s["name"]),
            "source": s["source"],
            "path": s["path"],
            "available": available,
            "missing_requirements": missing,
            "always": always_yaml,
            "pinned": s["name"] in pinned,
        })

    return JSONResponse({
        "skills": skills,
        "pinned_skills": pinned,
        "max_pinned_skills": max_pinned,
    })


async def api_skills_pin(request: Request):
    """Set the list of pinned skills."""
    data = await request.json()
    skill_names = data.get("pinned_skills", data.get("skills", []))

    cfg = agent_manager.config
    if not cfg:
        return JSONResponse({"error": "No config"}, status_code=400)

    max_pinned = cfg.agents.defaults.max_pinned_skills
    if len(skill_names) > max_pinned:
        return JSONResponse(
            {"error": f"Cannot pin more than {max_pinned} skills"},
            status_code=422,
        )

    try:
        loader = _get_loader()
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    known = {s["name"] for s in loader.list_skills(filter_unavailable=False)}
    invalid = [n for n in skill_names if n not in known]
    if invalid:
        return JSONResponse(
            {"error": f"Unknown skills: {', '.join(invalid)}"},
            status_code=422,
        )

    cfg.agents.defaults.pinned_skills = list(skill_names)
    from shibaclaw.config.loader import save_config
    save_config(cfg)
    logger.info("Pinned skills updated: {}", skill_names)

    return JSONResponse({"status": "updated", "pinned_skills": skill_names})


async def api_skills_delete(request: Request):
    """Delete a workspace skill by name."""
    name = request.path_params.get("name", "")
    if not name:
        return JSONResponse({"error": "Missing skill name"}, status_code=400)

    try:
        loader = _get_loader()
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    all_skills = loader.list_skills(filter_unavailable=False)
    skill = next((s for s in all_skills if s["name"] == name), None)
    if not skill:
        return JSONResponse({"error": f"Skill '{name}' not found"}, status_code=404)
    if skill["source"] != "workspace":
        return JSONResponse(
            {"error": "Cannot delete built-in skills"},
            status_code=403,
        )

    if not loader.delete_skill(name):
        return JSONResponse({"error": "Delete failed"}, status_code=500)

    cfg = agent_manager.config
    if cfg and name in cfg.agents.defaults.pinned_skills:
        cfg.agents.defaults.pinned_skills.remove(name)
        from shibaclaw.config.loader import save_config
        save_config(cfg)

    logger.info("Deleted workspace skill: {}", name)
    return JSONResponse({"status": "deleted", "name": name})


async def api_skills_import(request: Request):
    """Import skills from an uploaded .zip file."""
    form = await request.form()
    upload = form.get("file")
    if not upload:
        return JSONResponse({"error": "No file uploaded"}, status_code=400)

    conflict = str(form.get("conflict", "overwrite"))
    if conflict not in ("skip", "overwrite", "rename"):
        conflict = "overwrite"
    dry_run = str(form.get("dry_run", "false")).lower() in ("1", "true", "yes")

    try:
        zip_bytes = await upload.read()
    except Exception as e:
        return JSONResponse({"error": f"Failed to read upload: {e}"}, status_code=400)

    try:
        loader = _get_loader()
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    try:
        result = loader.import_skills_zip(zip_bytes, conflict=conflict, dry_run=dry_run)
    except Exception as e:
        logger.error("Skills import failed: {}", e)
        return JSONResponse({"error": f"Import failed: {e}"}, status_code=500)

    if not dry_run and result.get("imported"):
        logger.info("Imported {} skills: {}", result["imported_count"], result["imported"])

    return JSONResponse({"status": "ok", "dry_run": dry_run, **result})
