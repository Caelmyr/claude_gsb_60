"""错题集存储：每用户一个 JSON 分片，记录其未通过的题目。

设计要点：
  1. 评测终态为非 AC 时由评测引擎回调 record_failure() 自动收录；
  2. 同一道题只保留一条记录，反复做错只累加 wrong_count，不重复刷屏；
  3. 标记已掌握即删除记录；掌握后再次做错会重新收录（记录已删，自然重新进入）；
  4. 每用户独立分片 + 文件级锁（locked_update），多用户并发互不干扰。
"""
import os

from backend import config
from backend.storage import read_json, locked_update
from backend.utils import now_iso, sanitize_id

# 计入错题集的终态：SE（系统错误）不算用户的错题，其余非 AC 结果都算未通过
FAIL_STATUSES = {"WA", "TLE", "MLE", "RE", "CE", "OLE"}


def _path(user_id):
    return os.path.join(config.MISTAKES_DIR, f"{sanitize_id(user_id)}.json")


def record_failure(user_id, problem_id, status, submission_id):
    """评测未通过时收录错题；同一题去重，仅更新计数与最近状态。"""
    if status not in FAIL_STATUSES or not user_id or not problem_id:
        return

    def _upd(book):
        if not book:
            book = {"user_id": user_id, "items": []}
        items = book.setdefault("items", [])
        for it in items:
            if it.get("problem_id") == problem_id:
                it["wrong_count"] = int(it.get("wrong_count", 1)) + 1
                it["last_status"] = status
                it["last_submission_id"] = submission_id
                it["updated_at"] = now_iso()
                break
        else:
            items.append({
                "problem_id": problem_id,
                "wrong_count": 1,
                "last_status": status,
                "last_submission_id": submission_id,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            })
        return book

    locked_update(_path(user_id), _upd, default=None)


def list_mistakes(user_id):
    """返回某用户的错题列表（按最近出错时间倒序）。"""
    book = read_json(_path(user_id))
    items = list((book or {}).get("items", []))
    items.sort(key=lambda it: it.get("updated_at", ""), reverse=True)
    return items


def remove_mistake(user_id, problem_id):
    """标记已掌握：从错题集移除该题。返回是否确有记录被移除。"""
    removed = {"found": False}

    def _upd(book):
        if not book:
            return book
        items = book.get("items", [])
        kept = [it for it in items if it.get("problem_id") != problem_id]
        removed["found"] = len(kept) != len(items)
        book["items"] = kept
        return book

    locked_update(_path(user_id), _upd, default=None)
    return removed["found"]
