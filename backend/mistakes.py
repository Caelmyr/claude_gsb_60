"""错题集：每个用户一份，按用户 ID 分片存储。

自动维护规则（由评测引擎在裁决落定后调用）：
  - 提交被判为未通过（非 AC）→ 自动加入当前用户的错题集；
  - 同一道题反复出错只保留一条，更新最近错误信息，不重复刷屏；
  - 用户手动标记「已掌握」→ 从错题集移除；
  - 标记掌握后再次出错 → 重新加入（record 为幂等 upsert，天然支持）。

存储：data/mistakes/<user_id>.json
  {"user_id": ..., "items": [{problem_id, status, wrong_count,
                              first_wrong_at, last_wrong_at}]}
更新走 locked_update，按文件粒度加锁，不同用户之间互不阻塞。
"""
import os

from backend import config
from backend.storage import read_json, locked_update
from backend.utils import sanitize_id, now_iso, sort_list

# 记入错题集的「未通过」裁决（PENDING/JUDGING 为中间态，AC 为通过，均不记）
PASS_STATUS = "AC"
NON_FINAL_STATUSES = ("PENDING", "JUDGING")


def _mistakes_path(user_id):
    return os.path.join(config.MISTAKES_DIR, f"{sanitize_id(user_id)}.json")


def record_wrong(user_id, problem_id, status, at=None):
    """记录一次未通过提交。已在错题集中的题目只更新统计、不新增条目。

    返回 True 表示新加入，False 表示已存在（仅更新）。
    """
    if not user_id or not problem_id:
        return False
    if status == PASS_STATUS or status in NON_FINAL_STATUSES:
        return False
    ts = at or now_iso()
    result = {"added": False}

    def _upd(data):
        if data is None:
            data = {"user_id": user_id, "items": []}
        items = data.setdefault("items", [])
        for it in items:
            if it.get("problem_id") == problem_id:
                it["status"] = status
                it["wrong_count"] = int(it.get("wrong_count", 1)) + 1
                it["last_wrong_at"] = ts
                result["added"] = False
                return data
        items.append({
            "problem_id": problem_id,
            "status": status,
            "wrong_count": 1,
            "first_wrong_at": ts,
            "last_wrong_at": ts,
        })
        result["added"] = True
        return data

    locked_update(_mistakes_path(user_id), _upd, default=None)
    return result["added"]


def list_wrong(user_id):
    """返回用户错题集条目列表（按最近错误时间倒序）。"""
    data = read_json(_mistakes_path(user_id), default=None)
    if not data:
        return []
    return sort_list(data.get("items", []),
                     key=lambda it: it.get("last_wrong_at", ""), reverse=True)


def mark_mastered(user_id, problem_id):
    """标记已掌握：从错题集移除该题。返回是否移除成功。"""
    if not user_id or not problem_id:
        return False
    path = _mistakes_path(user_id)
    if not os.path.exists(path):
        return False
    result = {"removed": False}

    def _upd(data):
        if not data:
            return data
        items = data.get("items", [])
        kept = [it for it in items if it.get("problem_id") != problem_id]
        if len(kept) != len(items):
            result["removed"] = True
            data["items"] = kept
        return data

    locked_update(path, _upd, default=None)
    return result["removed"]
