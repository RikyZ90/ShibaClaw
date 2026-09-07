"""Skills management API endpoints."""

from __future__ import annotations

from loguru import logger
from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.agent.skills import SkillsLoader
from shibaclaw.webui.agent_manager import agent_manager


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

    profile_id = request.query_params.get("profile_id")
    cfg = agent_manager.config
    
    pinned = None
    if profile_id and cfg:
        try:
            from shibaclaw.agent.profiles import ProfileManager, DEFAULT_PROFILE_ID
            pm = ProfileManager(cfg.workspace_path)
            prof = pm.get_profile(profile_id or DEFAULT_PROFILE_ID)
            if prof and "pinned_skills" in prof:
                pinned = prof["pinned_skills"]
        except Exception:
            pass

    if pinned is None:
        pinned = cfg.agents.defaults.pinned_skills if cfg else []

    max_pinned = cfg.agents.defaults.max_pinned_skills if cfg else 5

    skills = []
    for s in loader.list_skills(filter_unavailable=False):
        meta = loader.get_skill_metadata(s["name"]) or {}
        skill_meta = loader._parse_shibaclaw_metadata(meta.get("metadata", ""))
        available = loader._check_requirements(skill_meta)
        missing = loader._get_missing_requirements(skill_meta) if not available else ""
        always_yaml = bool(skill_meta.get("always") or meta.get("always"))

        trust = {
            "name": s["name"],
            "description": meta.get("description", s["name"]),
            "path": s["path"],
            "source": s["source"],
        }
        caps = skill_meta.get("capabilities") or meta.get("capabilities")
        if caps:
            trust["capabilities"] = caps

        skills.append(
            {
                "name": s["name"],
                "description": meta.get("description", s["name"]),
                "source": s["source"],
                "path": s["path"],
                "available": available,
                "missing_requirements": missing,
                "always": always_yaml,
                "pinned": s["name"] in pinned,
                "trust": trust,
            }
        )

    return JSONResponse(
        {
            "skills": skills,
            "pinned_skills": pinned,
            "max_pinned_skills": max_pinned,
        }
    )


async def api_skills_workshop_list(request: Request):
    """List pending Skill Workshop proposals."""
    try:
        loader = _get_loader()
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    from shibaclaw.agent.skill_workshop import SkillWorkshop

    workshop = SkillWorkshop(loader.workspace)
    return JSONResponse({"pending": workshop.list_pending()})


async def api_skills_workshop_approve(request: Request):
    """Approve a pending workshop proposal by id."""
    data = await request.json()
    proposal_id = str(data.get("id") or "").strip()
    if not proposal_id:
        return JSONResponse({"error": "id is required"}, status_code=400)
    try:
        loader = _get_loader()
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    from shibaclaw.agent.skill_workshop import SkillWorkshop

    result = SkillWorkshop(loader.workspace).approve(proposal_id)
    if not result.get("ok"):
        return JSONResponse({"error": result.get("error", "failed")}, status_code=400)
    return JSONResponse({"status": "approved", **result})


async def api_skills_workshop_reject(request: Request):
    """Reject a pending workshop proposal by id."""
    data = await request.json()
    proposal_id = str(data.get("id") or "").strip()
    if not proposal_id:
        return JSONResponse({"error": "id is required"}, status_code=400)
    try:
        loader = _get_loader()
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    from shibaclaw.agent.skill_workshop import SkillWorkshop

    result = SkillWorkshop(loader.workspace).reject(proposal_id)
    if not result.get("ok"):
        return JSONResponse({"error": result.get("error", "failed")}, status_code=400)
    return JSONResponse({"status": "rejected", **result})


async def api_skills_pin(request: Request):
    """Set the list of pinned skills."""
    data = await request.json()
    skill_names = data.get("pinned_skills", data.get("skills", []))

    profile_id = data.get("profile_id")

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

    if profile_id:
        try:
            from shibaclaw.agent.profiles import ProfileManager
            pm = ProfileManager(cfg.workspace_path)
            pm.update_profile(profile_id, pinned_skills=list(skill_names))
            logger.info("Pinned skills updated for profile {}: {}", profile_id, skill_names)
            return JSONResponse({"status": "updated", "pinned_skills": skill_names, "profile_id": profile_id})
        except Exception as e:
            return JSONResponse({"error": f"Failed to update profile: {e}"}, status_code=500)

    cfg.agents.defaults.pinned_skills = list(skill_names)
    from shibaclaw.config.loader import save_config

    save_config(cfg)
    logger.info("Pinned skills updated globally: {}", skill_names)

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
