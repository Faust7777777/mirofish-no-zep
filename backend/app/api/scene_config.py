"""
场景配置（热配置）API

提供 4 个接口：
- GET    /api/scene-config/list           列出所有场景
- GET    /api/scene-config/<scene_name>   读取指定场景
- POST   /api/scene-config/save           保存（新建/覆盖）场景
- DELETE /api/scene-config/<scene_name>   删除场景
"""

import traceback

from flask import jsonify, request

from . import scene_config_bp
from ..services.scene_config_manager import (
    SceneConfigError,
    SceneConfigManager,
    ensure_default_scene,
)
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.scene_config')

# 启动时确保默认场景文件存在
ensure_default_scene()


@scene_config_bp.route('/list', methods=['GET'])
def list_scene_configs():
    """列出所有已保存的场景配置摘要。"""
    try:
        scenes = SceneConfigManager.list_scenes()
        return jsonify({"success": True, "data": scenes, "count": len(scenes)})
    except Exception as e:
        logger.error(f"列出场景配置失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@scene_config_bp.route('/save', methods=['POST'])
def save_scene_config():
    """保存（新建或覆盖）场景配置。"""
    try:
        payload = request.get_json() or {}
        normalized = SceneConfigManager.save_scene(payload)
        return jsonify({"success": True, "data": normalized})
    except SceneConfigError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"保存场景配置失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@scene_config_bp.route('/<path:scene_name>', methods=['GET'])
def get_scene_config(scene_name: str):
    """读取指定场景配置的完整 JSON。"""
    try:
        scene = SceneConfigManager.get_scene(scene_name)
        if scene is None:
            return jsonify({
                "success": False,
                "error": f"场景不存在：{scene_name}",
            }), 404
        return jsonify({"success": True, "data": scene})
    except SceneConfigError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"读取场景配置失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@scene_config_bp.route('/<path:scene_name>', methods=['DELETE'])
def delete_scene_config(scene_name: str):
    """删除指定场景配置。"""
    try:
        deleted = SceneConfigManager.delete_scene(scene_name)
        if not deleted:
            return jsonify({
                "success": False,
                "error": f"场景不存在：{scene_name}",
            }), 404
        return jsonify({"success": True, "data": {"scene_name": scene_name}})
    except SceneConfigError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"删除场景配置失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500
