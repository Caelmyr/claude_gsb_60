"""错题集 API：查看我的错题、标记已掌握。"""
import os

from flask import Blueprint, request

from backend import config
from backend import mistakes as store
from backend.api import ok, err, require_auth
from backend.storage import read_json

mistakes_bp = Blueprint("mistakes", __name__)


@mistakes_bp.get("/mistakes")
@require_auth
def list_my_mistakes():
    """当前用户的错题集（每用户各自一份，互不可见）。"""
    items = store.list_mistakes(request.user["id"])
    out = []
    for it in items:
        p = read_json(os.path.join(config.PROBLEMS_DIR, f"{it['problem_id']}.json"))
        out.append({
            **it,
            "title": (p or {}).get("title", it["problem_id"]),
            "difficulty": (p or {}).get("difficulty"),
            "tags": (p or {}).get("tags", []),
            "exists": p is not None,
        })
    return ok({"total": len(out), "items": out})


@mistakes_bp.post("/mistakes/<problem_id>/master")
@require_auth
def master(problem_id):
    """标记已掌握：从错题集移除；之后再次做错会自动重新收录。"""
    if store.remove_mistake(request.user["id"], problem_id):
        return ok({"problem_id": problem_id})
    return err("该题不在错题集中", 404)
