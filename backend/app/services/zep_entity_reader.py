"""
Zep实体读取与过滤服务 (MiroFish 本地魔改版)
功能：彻底拦截所有 Zep 云端请求，确保本地模拟流程 100% 跑通。
"""

import time
from typing import Dict, Any, List, Optional, Set, Callable, TypeVar
from dataclasses import dataclass, field

# 虽然不连云端，但保留类型定义以维持系统架构
@dataclass
class EntityNode:
    """实体节点数据结构"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }

@dataclass
class FilteredEntities:
    """过滤后的实体集合"""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }

class ZepEntityReader:
    """
    Zep实体读取与过滤服务
    【逻辑手术版】：已切断所有 httpx 联网调用
    """
    
    def __init__(self, api_key: Optional[str] = None):
        # 不再初始化真实的 Zep 客户端，防止它在后台偷偷联网
        self.client = None
        print(">>> [本地模式] ZepEntityReader 已就绪，已绕过 API Key 验证")

    def _call_with_retry(self, func, operation_name, **kwargs):
        """【拦截】屏蔽重试机制"""
        return None

    def get_all_nodes(self, graph_id: str) -> List[Any]:
        """【拦截】防止 10061 报错：直接返回空仓库"""
        print(f">>> 拦截节点读取请求，图谱 ID: {graph_id}")
        return []

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """【拦截】防止边读取报错"""
        print(f">>> 拦截边读取请求，图谱 ID: {graph_id}")
        return []

    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """【拦截】防止单个节点边请求报错"""
        return []

    def filter_defined_entities(self, graph_id: str, defined_entity_types: Optional[List[str]] = None, enrich_with_edges: bool = True) -> FilteredEntities:
        """【关键拦截】让模拟准备阶段顺利通过，返回一个空的 FilteredEntities 对象"""
        print(f">>> 绕过实体过滤逻辑，强制返回成功，ID: {graph_id}")
        return FilteredEntities(
            entities=[],
            entity_types=set(),
            total_count=0,
            filtered_count=0
        )

    def get_entity_with_context(self, graph_id: str, entity_uuid: str) -> Optional[EntityNode]:
        """【拦截】防止模拟运行时的单节点查询报错"""
        return None

    def get_entities_by_type(self, graph_id: str, entity_type: str, enrich_with_edges: bool = True) -> List[EntityNode]:
        """【拦截】防止类型查询报错"""
        return []


