"""错题集 API：仅操作当前登录用户自己的错题集，用户间互不干扰。"""
import os

from flask import Blueprint, request

from backend import config
from backend.api import ok, err, require_auth
from backend.storage import read_json
from backend.mistakes import list_wrong, mark_mastered

mistakes_bp = Blueprint("mistakes", __name__)


def _problem_brief(problem_id):
    """补充列表展示所需的题目信息；题目已被删除时返回 None。"""
    p = read_json(os.path.join(config.PROBLEMS_DIR, f"{problem_id}.json"))
    if not p:
        return None
    return {
        "id": p.get("id", problem_id),
        "title": p.get("title", ""),
        "difficulty": p.get("difficulty", 1),
        "tags": p.get("tags", []),
    }


@mistakes_bp.get("/mistakes")
@require_auth
def my_mistakes():
    user_id = request.user["id"]
    items = []
    for it in list_wrong(user_id):
        row = dict(it)
        row["problem"] = _problem_brief(it.get("problem_id"))
        items.append(row)
    return ok({"total": len(items), "items": items})


@mistakes_bp.post("/mistakes/<problem_id>/mastered")
@require_auth
def mastered(problem_id):
    if mark_mastered(request.user["id"], problem_id):
        return ok({"problem_id": problem_id})
    return err("该题不在错题集中", 404, 404)
