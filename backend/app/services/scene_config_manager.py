"""
场景配置（热配置）管理器

将原本硬编码在 SimulationManager.prepare_simulation 中的场景信息
（角色列表、触发事件、场景描述）抽离为可视化、可热加载的 JSON 文件，
让平台从「《理想国》专用工具」变成「任意哲学思想实验通用模拟器」。

JSON 文件存放路径： backend/app/config/scene_configs/<场景名>.json
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger('mirofish.scene_config')


# 角色字段
ACTOR_FIELDS = ("name", "label", "summary", "personality")

# 初始帖子字段
POST_FIELDS = ("content", "poster_type", "platform")

# 文件名安全字符
_NAME_SAFE_RE = re.compile(r"[^\w\u4e00-\u9fff\-]", re.UNICODE)


class SceneConfigError(ValueError):
    """场景配置参数错误。"""


class SceneConfigManager:
    """场景配置 JSON 文件的读写管理。"""

    # 配置目录：backend/app/config/scene_configs/
    CONFIG_DIR = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'config', 'scene_configs')
    )

    @classmethod
    def _ensure_dir(cls) -> None:
        os.makedirs(cls.CONFIG_DIR, exist_ok=True)

    @classmethod
    def _safe_filename(cls, scene_name: str) -> str:
        """把任意场景名转成安全文件名（中文保留，特殊字符替换为 _）。"""
        if not scene_name or not scene_name.strip():
            raise SceneConfigError("场景名不能为空")
        cleaned = _NAME_SAFE_RE.sub("_", scene_name.strip())
        if not cleaned:
            raise SceneConfigError("场景名无效")
        return cleaned + ".json"

    @classmethod
    def _config_path(cls, scene_name: str) -> str:
        cls._ensure_dir()
        return os.path.join(cls.CONFIG_DIR, cls._safe_filename(scene_name))

    @classmethod
    def list_scenes(cls) -> List[Dict[str, Any]]:
        """列出所有已保存的场景。返回包含场景名、actor 数量、修改时间的摘要列表。"""
        cls._ensure_dir()
        scenes: List[Dict[str, Any]] = []
        for fname in sorted(os.listdir(cls.CONFIG_DIR)):
            if not fname.endswith('.json'):
                continue
            full_path = os.path.join(cls.CONFIG_DIR, fname)
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                scenes.append({
                    "scene_name": data.get("scene_name", fname[:-5]),
                    "file_name": fname,
                    "actors_count": len(data.get("actors", [])),
                    "initial_posts_count": len(data.get("initial_posts", [])),
                    "updated_at": datetime.fromtimestamp(
                        os.path.getmtime(full_path)
                    ).isoformat(),
                })
            except Exception as e:
                logger.warning(f"读取场景文件失败: {fname}, error={e}")
        return scenes

    @classmethod
    def get_scene(cls, scene_name: str) -> Optional[Dict[str, Any]]:
        """读取指定场景的完整 JSON。不存在时返回 None。"""
        path = cls._config_path(scene_name)
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @classmethod
    def save_scene(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """校验并保存场景配置。返回标准化后的 JSON。"""
        scene_name = (payload.get("scene_name") or "").strip()
        if not scene_name:
            raise SceneConfigError("scene_name 不能为空")

        scene_description = (payload.get("scene_description") or "").strip()
        scene_event = (payload.get("scene_event") or "").strip()

        actors = cls._normalize_actors(payload.get("actors", []))
        initial_posts = cls._normalize_initial_posts(
            payload.get("initial_posts", []),
            actors=actors,
        )

        normalized = {
            "scene_name": scene_name,
            "scene_description": scene_description,
            "scene_event": scene_event,
            "actors": actors,
            "initial_posts": initial_posts,
            "updated_at": datetime.now().isoformat(),
        }

        path = cls._config_path(scene_name)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存场景配置: {scene_name} -> {path}")
        return normalized

    @classmethod
    def delete_scene(cls, scene_name: str) -> bool:
        """删除指定场景。返回是否真的删除了文件。"""
        path = cls._config_path(scene_name)
        if not os.path.exists(path):
            return False
        os.remove(path)
        logger.info(f"已删除场景配置: {scene_name}")
        return True

    # ---------- 校验工具 ----------

    @staticmethod
    def _normalize_actors(actors_raw: Any) -> List[Dict[str, str]]:
        if not isinstance(actors_raw, list) or not actors_raw:
            raise SceneConfigError("actors 必须是非空数组")

        normalized: List[Dict[str, str]] = []
        seen_names = set()
        for idx, actor in enumerate(actors_raw):
            if not isinstance(actor, dict):
                raise SceneConfigError(f"actors[{idx}] 必须是对象")

            name = (actor.get("name") or "").strip()
            label = (actor.get("label") or "").strip()
            summary = (actor.get("summary") or "").strip()
            personality = (actor.get("personality") or "").strip()

            if not name:
                raise SceneConfigError(f"actors[{idx}].name 不能为空")
            if not label:
                raise SceneConfigError(f"actors[{idx}].label 不能为空")
            if name in seen_names:
                raise SceneConfigError(f"角色名重复：{name}")
            seen_names.add(name)

            normalized.append({
                "name": name,
                "label": label,
                "summary": summary,
                "personality": personality,
            })
        return normalized

    @staticmethod
    def _normalize_initial_posts(
        posts_raw: Any,
        actors: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        if not isinstance(posts_raw, list):
            raise SceneConfigError("initial_posts 必须是数组")
        if len(posts_raw) > 5:
            raise SceneConfigError("initial_posts 最多 5 条")

        valid_labels = {a["label"] for a in actors}
        valid_platforms = {"twitter", "reddit", "both"}

        normalized: List[Dict[str, str]] = []
        for idx, post in enumerate(posts_raw):
            if not isinstance(post, dict):
                raise SceneConfigError(f"initial_posts[{idx}] 必须是对象")

            content = (post.get("content") or "").strip()
            poster_type = (post.get("poster_type") or "").strip()
            platform = (post.get("platform") or "both").strip().lower()

            if not content:
                raise SceneConfigError(f"initial_posts[{idx}].content 不能为空")
            if poster_type and poster_type not in valid_labels:
                raise SceneConfigError(
                    f"initial_posts[{idx}].poster_type 必须来自当前 actors 的 label：{poster_type}"
                )
            if platform not in valid_platforms:
                raise SceneConfigError(
                    f"initial_posts[{idx}].platform 必须是 twitter/reddit/both"
                )

            normalized.append({
                "content": content,
                "poster_type": poster_type,
                "platform": platform,
            })
        return normalized


# 默认场景：当前硬编码的《理想国》17 人，作为预置示例 / 向后兼容回退
DEFAULT_REPUBLIC_SCENE: Dict[str, Any] = {
    "scene_name": "柏拉图《理想国》第三卷——禁诗实验",
    "scene_description": (
        "古希腊雅典城邦内的哲学思想实验：城邦推行严格的诗歌审查制度，"
        "禁止描写英雄软弱、恐惧或对死亡的恐惧的诗句，认为它们会动摇护卫者的勇气。"
    ),
    "scene_event": "一首被禁止的诗歌在城邦中悄悄流传，引发各阶层人物的反应与争论。",
    "actors": [
        {"name": "哲人长老", "label": "Philosopher", "summary": "60岁，深谙审查逻辑，视其为必要统治工具。", "personality": "权威"},
        {"name": "哲人学徒", "label": "Philosopher", "summary": "22岁，对道德直觉与条件反射的界限感到困惑。", "personality": "不安"},
        {"name": "老护卫",   "label": "Guardian",    "summary": "45岁，从军20年，极度厌恶描写懦弱的诗句。", "personality": "刚毅"},
        {"name": "年轻护卫甲","label": "Guardian",   "summary": "20岁，读诗后感到真实恐惧，陷入沉默。", "personality": "内敛"},
        {"name": "年轻护卫乙","label": "Guardian",   "summary": "21岁，公开激烈斥责，私下承认战场恐惧。", "personality": "伪善"},
        {"name": "年轻护卫丙","label": "Guardian",   "summary": "19岁，随大流，观察他人立场。", "personality": "从众"},
        {"name": "女护卫",   "label": "Guardian",    "summary": "28岁，被压抑情感多年，被诗中脆弱的一幕触动。", "personality": "隐忍"},
        {"name": "护卫队长", "label": "Guardian",    "summary": "38岁，纯粹的管理者，准备上报哲人。", "personality": "务实"},
        {"name": "受伤的老兵","label": "Guardian",   "summary": "50岁，深知战场真实，认为禁诗比教材真实。", "personality": "沉默"},
        {"name": "新兵",     "label": "Guardian",    "summary": "17岁，教育体系的完美成品，面对冲突极度焦虑。", "personality": "焦虑"},
        {"name": "老工匠",   "label": "Worker",      "summary": "55岁，务实派，认为英雄恐惧是人之常情。", "personality": "随和"},
        {"name": "年轻农民", "label": "Worker",      "summary": "23岁，未受精英教育，不理解禁书逻辑。", "personality": "质朴"},
        {"name": "市集小贩", "label": "Worker",      "summary": "35岁，禁诗传播源头，好奇又害怕。", "personality": "投机"},
        {"name": "织布工",   "label": "Worker",      "summary": "30岁，认为承认软弱需要更大的勇气。", "personality": "坚定"},
        {"name": "外来商人", "label": "Outsider",    "summary": "来自无审查城邦，完全无法理解这里的禁书制度。", "personality": "精明"},
        {"name": "外来诗人", "label": "Outsider",    "summary": "禁诗作者，认为描写真实人性即是道德。", "personality": "反叛"},
        {"name": "流浪哲学者","label": "Outsider",   "summary": "游历者，清醒的观察者，不干预只记录。", "personality": "深邃"},
    ],
    "initial_posts": [
        {
            "content": "你们听说了吗？市集那边在传一首被禁的诗，写的是英雄在战场上的恐惧……我没看，我发誓没看。",
            "poster_type": "Outsider",
            "platform": "both",
        },
    ],
}


def ensure_default_scene() -> None:
    """如果默认场景文件不存在，写一份作为预置示例。"""
    try:
        path = SceneConfigManager._config_path(DEFAULT_REPUBLIC_SCENE["scene_name"])
        if not os.path.exists(path):
            SceneConfigManager.save_scene(DEFAULT_REPUBLIC_SCENE)
    except Exception as e:
        logger.warning(f"写入默认场景失败: {e}")
