"""
Agent 上下文注入工具

为每个活跃 Agent 在 env.step() 之前临时把"最近发言摘要"附加到其
system_message 末尾，让 Agent 在不依赖 Zep 记忆系统的情况下也能
回应他人的发言（修复 Bug 2：角色之间无互动，各说各话）。

使用方式：
    injector = RecentContextInjector(db_path, platform="twitter")
    with injector.inject(active_agents):
        await env.step(actions)
"""

import os
import sqlite3
import contextlib
from typing import Iterable, List, Tuple, Optional


# 每次注入读取的最近发言条数
DEFAULT_LIMIT = 10
# 单条发言截断长度，避免提示词过长
MAX_CONTENT_CHARS = 200


def _fetch_recent_twitter(db_path: str, limit: int) -> List[Tuple[str, str]]:
    """读取 Twitter 数据库的最近发言。返回 [(作者, 内容), ...]"""
    if not os.path.exists(db_path):
        return []
    rows: List[Tuple[str, str]] = []
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COALESCE(u.name, u.user_name, 'anon'), p.content
            FROM post p
            LEFT JOIN user u ON p.user_id = u.user_id
            WHERE p.content IS NOT NULL AND p.content != ''
            ORDER BY p.post_id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = list(cur.fetchall())
        conn.close()
    except Exception:
        return []
    return rows


def _fetch_recent_reddit(db_path: str, limit: int) -> List[Tuple[str, str]]:
    """读取 Reddit 数据库的最近帖子+评论。返回 [(作者, 内容), ...]"""
    if not os.path.exists(db_path):
        return []
    rows: List[Tuple[str, str]] = []
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        # 帖子
        try:
            cur.execute(
                """
                SELECT COALESCE(u.name, u.user_name, 'anon'), p.content
                FROM post p
                LEFT JOIN user u ON p.user_id = u.user_id
                WHERE p.content IS NOT NULL AND p.content != ''
                ORDER BY p.post_id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows.extend(cur.fetchall())
        except sqlite3.OperationalError:
            pass
        # 评论
        try:
            cur.execute(
                """
                SELECT COALESCE(u.name, u.user_name, 'anon'), c.content
                FROM comment c
                LEFT JOIN user u ON c.user_id = u.user_id
                WHERE c.content IS NOT NULL AND c.content != ''
                ORDER BY c.comment_id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows.extend(cur.fetchall())
        except sqlite3.OperationalError:
            pass
        conn.close()
    except Exception:
        return []
    # 综合按出现顺序截取最近 N 条
    return rows[:limit]


def _fetch_recent(platform: str, db_path: str, limit: int) -> List[Tuple[str, str]]:
    if platform == "twitter":
        return _fetch_recent_twitter(db_path, limit)
    return _fetch_recent_reddit(db_path, limit)


def _build_context_block(rows: List[Tuple[str, str]], platform: str) -> str:
    """根据最近发言生成提示词块。"""
    if not rows:
        return ""
    place = "广场" if platform == "twitter" else "话题社区"
    lines = [f"\n\n## 你刚刚在{place}上看到了这些讨论："]
    for name, content in rows:
        if not content:
            continue
        snippet = content.replace("\n", " ").strip()
        if len(snippet) > MAX_CONTENT_CHARS:
            snippet = snippet[:MAX_CONTENT_CHARS] + "…"
        lines.append(f"- [{name}]说：{snippet}")
    lines.append(
        "\n请以你自己的身份、性格和立场，自然地回应或发表看法。"
        "不要重复别人说过的话，可以直接引用、反驳、追问或保持沉默。"
    )
    return "\n".join(lines)


def _get_system_message_attr(agent):
    """
    OASIS 内部使用 camel-ai 的 ChatAgent，
    其 system_message 通常通过 _system_message 或 system_message 暴露。
    返回 (持有者对象, 原始内容字符串) 或 (None, None)。
    """
    candidates = ("_system_message", "system_message")
    for attr in candidates:
        msg = getattr(agent, attr, None)
        if msg is None:
            continue
        # camel-ai 的 BaseMessage 有 .content
        content = getattr(msg, "content", None)
        if content is not None:
            return (msg, content, attr)
    return (None, None, None)


class RecentContextInjector:
    """根据数据库最近发言，临时往 Agent 的 system_message 注入上下文。"""

    def __init__(self, db_path: str, platform: str, limit: int = DEFAULT_LIMIT):
        self.db_path = db_path
        self.platform = platform
        self.limit = limit

    @contextlib.contextmanager
    def inject(self, agents: Iterable):
        """上下文管理器：进入时追加最近发言，退出时恢复原 system_message。"""
        rows = _fetch_recent(self.platform, self.db_path, self.limit)
        block = _build_context_block(rows, self.platform)

        backups = []  # [(message_obj, original_content)]

        if block:
            for agent in agents:
                msg_obj, original, _attr = _get_system_message_attr(agent)
                if msg_obj is None:
                    continue
                try:
                    # camel-ai 的 BaseMessage.content 是字符串属性，可直接覆盖
                    msg_obj.content = (original or "") + block
                    backups.append((msg_obj, original))
                except Exception:
                    # 安全起见，不让注入失败影响主流程
                    continue
        try:
            yield
        finally:
            for msg_obj, original in backups:
                try:
                    msg_obj.content = original
                except Exception:
                    pass
