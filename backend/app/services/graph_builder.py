"""
图谱构建服务
接口2：使用Zep API构建Standalone Graph
"""

import os
import uuid
import time
import threading
import json
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

from zep_cloud.client import Zep
from zep_cloud import EpisodeData, EntityEdgeSourceTarget

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..models.project import ProjectManager
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges
from .text_processor import TextProcessor
from ..utils.locale import t, get_locale, set_locale


@dataclass
class GraphInfo:
    """图谱信息"""
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class GraphBuilderService:
    """
    图谱构建服务
    负责调用Zep API构建知识图谱
    """
    
    LOCAL_GRAPH_DIR = os.path.join(Config.UPLOAD_FOLDER, 'graphs')

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if Config.USE_ZEP and not self.api_key:
            raise ValueError("ZEP_API_KEY 未配置")

        self.client = Zep(api_key=self.api_key) if Config.USE_ZEP else None
        self.task_manager = TaskManager()

    @classmethod
    def _ensure_local_graph_dir(cls) -> None:
        os.makedirs(cls.LOCAL_GRAPH_DIR, exist_ok=True)

    @classmethod
    def _get_local_graph_path(cls, graph_id: str) -> str:
        cls._ensure_local_graph_dir()
        return os.path.join(cls.LOCAL_GRAPH_DIR, f"{graph_id}.json")

    @classmethod
    def append_local_graph_facts(
        cls,
        graph_id: str,
        facts: List[Dict[str, Any]],
        source: str = "local_simulation_memory",
    ) -> Dict[str, Any]:
        graph_data = cls.get_local_graph_data(graph_id)
        nodes = graph_data.setdefault("nodes", [])
        edges = graph_data.setdefault("edges", [])
        node_by_name = {node.get("name"): node for node in nodes if node.get("name")}

        def ensure_node(name: str, summary: str = "") -> Dict[str, Any]:
            if name in node_by_name:
                node = node_by_name[name]
                if summary and not node.get("summary"):
                    node["summary"] = summary[:500]
                return node

            node = {
                "uuid": f"{graph_id}_sim_node_{len(nodes)}",
                "name": name,
                "labels": ["SimulationAgent"],
                "summary": summary[:500] if summary else f"{name} 在模拟过程中产生了行为记录。",
                "attributes": {
                    "source": source,
                },
            }
            nodes.append(node)
            node_by_name[name] = node
            return node

        for item in facts:
            fact_text = (item.get("fact") or "").strip()
            if not fact_text:
                continue

            agent_name = item.get("agent_name") or f"Agent_{item.get('agent_id', 'unknown')}"
            source_node = ensure_node(agent_name, fact_text)
            target_name = item.get("target_name") or agent_name
            target_node = ensure_node(target_name, fact_text if target_name != agent_name else "")

            edge_index = len(edges)
            edges.append({
                "uuid": f"{graph_id}_sim_edge_{edge_index}",
                "name": item.get("action_type") or "SIMULATION_ACTION",
                "fact": fact_text[:2000],
                "source_node_uuid": source_node["uuid"],
                "target_node_uuid": target_node["uuid"],
                "created_at": item.get("timestamp") or datetime.now().isoformat(),
                "valid_at": item.get("timestamp"),
                "invalid_at": None,
                "expired_at": None,
                "episodes": [
                    f"{item.get('platform', 'simulation')}_round_{item.get('round_num', 0)}"
                ],
                "attributes": {
                    "source": source,
                    "platform": item.get("platform"),
                    "round_num": item.get("round_num"),
                    "agent_id": item.get("agent_id"),
                    "agent_name": agent_name,
                    "action_type": item.get("action_type"),
                },
            })

        graph_data["node_count"] = len(nodes)
        graph_data["edge_count"] = len(edges)
        graph_data["entity_types"] = sorted({label for node in nodes for label in node.get("labels", []) if label})

        with open(cls._get_local_graph_path(graph_id), 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)

        return graph_data

    @classmethod
    def _extract_entity_candidates(cls, text: str) -> List[str]:
        pattern = re.compile(r'[\u4e00-\u9fff]{2,8}|[A-Za-z][A-Za-z0-9_-]{2,24}')
        blacklist = {
            '一个', '一种', '一些', '这个', '那个', '我们', '你们', '他们', '她们', '以及', '因为',
            '所以', '如果', '进行', '通过', '对于', '可以', '已经', '需要', '报告', '分析', '模拟',
            '平台', '内容', '信息', '系统', '问题', '结果', '阶段', '图谱', '城邦', '教育', '英雄',
        }
        counts: Dict[str, int] = {}
        for match in pattern.findall(text or ''):
            candidate = match.strip()
            if len(candidate) < 2 or candidate in blacklist or candidate.isdigit():
                continue
            counts[candidate] = counts.get(candidate, 0) + 1

        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return [name for name, _ in ranked[:18]]

    @classmethod
    def _build_local_graph_document(
        cls,
        graph_id: str,
        text: str,
        ontology: Optional[Dict[str, Any]] = None,
        graph_name: str = "Local Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> Dict[str, Any]:
        normalized_text = TextProcessor.preprocess_text(text or "")
        chunks = TextProcessor.split_text(normalized_text, chunk_size, chunk_overlap) if normalized_text else []

        entity_types = [item.get("name", "Entity") for item in (ontology or {}).get("entity_types", []) if item.get("name")]
        primary_label = entity_types[0] if entity_types else "Entity"

        entity_names = cls._extract_entity_candidates(normalized_text)
        nodes: List[Dict[str, Any]] = []
        for idx, name in enumerate(entity_names):
            related_chunks = [chunk for chunk in chunks if name in chunk][:2]
            summary = related_chunks[0][:240] if related_chunks else f"{name} 在项目文本中被多次提及。"
            nodes.append({
                "uuid": f"{graph_id}_node_{idx}",
                "name": name,
                "labels": [primary_label],
                "summary": summary,
                "attributes": {
                    "mentions": len(related_chunks) or normalized_text.count(name),
                    "source": "local_file_graph",
                },
            })

        edges: List[Dict[str, Any]] = []
        for idx, chunk in enumerate(chunks):
            fact = chunk.strip()
            if not fact:
                continue

            matched_nodes = [node for node in nodes if node["name"] in fact]
            if len(matched_nodes) >= 2:
                source = matched_nodes[0]
                target = matched_nodes[1]
                edge_name = "CO_OCCURS"
            elif matched_nodes:
                source = matched_nodes[0]
                target = matched_nodes[0]
                edge_name = "MENTIONED_IN"
            else:
                if not nodes:
                    fallback_name = f"文本片段{idx + 1}"
                    node_uuid = f"{graph_id}_chunk_{idx}"
                    nodes.append({
                        "uuid": node_uuid,
                        "name": fallback_name,
                        "labels": ["TextChunk"],
                        "summary": fact[:240],
                        "attributes": {
                            "chunk_index": idx,
                            "source": "local_file_graph",
                        },
                    })
                source = nodes[min(idx, len(nodes) - 1)]
                target = source
                edge_name = "TEXT_EVIDENCE"

            edges.append({
                "uuid": f"{graph_id}_edge_{idx}",
                "name": edge_name,
                "fact": fact[:500],
                "source_node_uuid": source["uuid"],
                "target_node_uuid": target["uuid"],
                "created_at": None,
                "valid_at": None,
                "invalid_at": None,
                "expired_at": None,
                "episodes": [f"chunk_{idx + 1}"],
            })

        if not nodes and normalized_text:
            nodes.append({
                "uuid": f"{graph_id}_root",
                "name": graph_name,
                "labels": ["Document"],
                "summary": normalized_text[:240],
                "attributes": {
                    "source": "local_file_graph",
                },
            })

        return {
            "graph_id": graph_id,
            "graph_name": graph_name,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "entity_types": sorted({label for node in nodes for label in node.get("labels", []) if label}),
            "text_length": len(normalized_text),
        }

    @classmethod
    def save_local_graph(
        cls,
        graph_id: str,
        text: str,
        ontology: Optional[Dict[str, Any]] = None,
        graph_name: str = "Local Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> Dict[str, Any]:
        graph_data = cls._build_local_graph_document(
            graph_id=graph_id,
            text=text,
            ontology=ontology,
            graph_name=graph_name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        with open(cls._get_local_graph_path(graph_id), 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)
        return graph_data

    @classmethod
    def load_local_graph(cls, graph_id: str) -> Optional[Dict[str, Any]]:
        graph_path = cls._get_local_graph_path(graph_id)
        if not os.path.exists(graph_path):
            return None
        with open(graph_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @classmethod
    def get_local_graph_data(cls, graph_id: str) -> Dict[str, Any]:
        graph_data = cls.load_local_graph(graph_id)
        if graph_data:
            return graph_data

        for project in ProjectManager.list_projects(limit=500):
            if project.graph_id != graph_id:
                continue
            text = ProjectManager.get_extracted_text(project.project_id) or ""
            graph_data = cls.save_local_graph(
                graph_id=graph_id,
                text=text,
                ontology=project.ontology,
                graph_name=project.name,
                chunk_size=project.chunk_size,
                chunk_overlap=project.chunk_overlap,
            )
            return graph_data

        return {
            "graph_id": graph_id,
            "graph_name": graph_id,
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0,
            "entity_types": [],
            "text_length": 0,
        }
    
    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3
    ) -> str:
        """
        异步构建图谱
        
        Args:
            text: 输入文本
            ontology: 本体定义（来自接口1的输出）
            graph_name: 图谱名称
            chunk_size: 文本块大小
            chunk_overlap: 块重叠大小
            batch_size: 每批发送的块数量
            
        Returns:
            任务ID
        """
        # 创建任务
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            }
        )
        
        # Capture locale before spawning background thread
        current_locale = get_locale()

        # 在后台线程中执行构建
        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size, current_locale)
        )
        thread.daemon = True
        thread.start()
        
        return task_id
    
    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int,
        locale: str = 'zh'
    ):
        """图谱构建工作线程"""
        set_locale(locale)
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message=t('progress.startBuildingGraph')
            )
            
            # 1. 创建图谱
            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(
                task_id,
                progress=10,
                message=t('progress.graphCreated', graphId=graph_id)
            )
            
            # 2. 设置本体
            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(
                task_id,
                progress=15,
                message=t('progress.ontologySet')
            )
            
            # 3. 文本分块
            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id,
                progress=20,
                message=t('progress.textSplit', count=total_chunks)
            )
            
            # 4. 分批发送数据
            episode_uuids = self.add_text_batches(
                graph_id, chunks, batch_size,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 0.4),  # 20-60%
                    message=msg
                )
            )
            
            # 5. 等待Zep处理完成
            self.task_manager.update_task(
                task_id,
                progress=60,
                message=t('progress.waitingZepProcess')
            )
            
            self._wait_for_episodes(
                episode_uuids,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=60 + int(prog * 0.3),  # 60-90%
                    message=msg
                )
            )
            
            # 6. 获取图谱信息
            self.task_manager.update_task(
                task_id,
                progress=90,
                message=t('progress.fetchingGraphInfo')
            )
            
            graph_info = self._get_graph_info(graph_id)
            
            # 完成
            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info.to_dict(),
                "chunks_processed": total_chunks,
            })
            
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.task_manager.fail_task(task_id, error_msg)
    
    def create_graph(self, name: str) -> str:
        """【手术】强行返回本地 ID，不连 Zep"""
        graph_id = f"local_{uuid.uuid4().hex[:8]}"
        print(f">>> 绕过 Zep，创建本地虚拟 ID: {graph_id}")
        return graph_id
        
        # --- 手术开始：把下面这段全部加井号注释掉 ---
        # self.client.graph.create(
        #     graph_id=graph_id,
        #     name=name,
        #     description="MiroFish Social Simulation Graph"
        # )
        # --- 手术结束 ---

        # 打印一行字，让我们在黑窗口里看到它跳过了
        print(f">>> 已跳过 Zep 云端创建，使用本地 ID: {graph_id}")
        
        return graph_id
    
    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """【手术】禁止上传本体到云端"""
        print(">>> 绕过 Zep 本体上传")
        return # 这一行最关键，后面的代码全都不会执行了

        import warnings
        from typing import Optional
        from pydantic import Field
        from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel
        
        # 抑制 Pydantic v2 关于 Field(default=None) 的警告
        # 这是 Zep SDK 要求的用法，警告来自动态类创建，可以安全忽略
        warnings.filterwarnings('ignore', category=UserWarning, module='pydantic')
        
        # Zep 保留名称，不能作为属性名
        RESERVED_NAMES = {'uuid', 'name', 'group_id', 'name_embedding', 'summary', 'created_at'}
        
        def safe_attr_name(attr_name: str) -> str:
            """将保留名称转换为安全名称"""
            if attr_name.lower() in RESERVED_NAMES:
                return f"entity_{attr_name}"
            return attr_name
        
        # 动态创建实体类型
        entity_types = {}
        for entity_def in ontology.get("entity_types", []):
            name = entity_def["name"]
            description = entity_def.get("description", f"A {name} entity.")
            
            # 创建属性字典和类型注解（Pydantic v2 需要）
            attrs = {"__doc__": description}
            annotations = {}
            
            for attr_def in entity_def.get("attributes", []):
                attr_name = safe_attr_name(attr_def["name"])  # 使用安全名称
                attr_desc = attr_def.get("description", attr_name)
                # Zep API 需要 Field 的 description，这是必需的
                attrs[attr_name] = Field(description=attr_desc, default=None)
                annotations[attr_name] = Optional[EntityText]  # 类型注解
            
            attrs["__annotations__"] = annotations
            
            # 动态创建类
            entity_class = type(name, (EntityModel,), attrs)
            entity_class.__doc__ = description
            entity_types[name] = entity_class
        
        # 动态创建边类型
        edge_definitions = {}
        for edge_def in ontology.get("edge_types", []):
            name = edge_def["name"]
            description = edge_def.get("description", f"A {name} relationship.")
            
            # 创建属性字典和类型注解
            attrs = {"__doc__": description}
            annotations = {}
            
            for attr_def in edge_def.get("attributes", []):
                attr_name = safe_attr_name(attr_def["name"])  # 使用安全名称
                attr_desc = attr_def.get("description", attr_name)
                # Zep API 需要 Field 的 description，这是必需的
                attrs[attr_name] = Field(description=attr_desc, default=None)
                annotations[attr_name] = Optional[str]  # 边属性用str类型
            
            attrs["__annotations__"] = annotations
            
            # 动态创建类
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            edge_class = type(class_name, (EdgeModel,), attrs)
            edge_class.__doc__ = description
            
            # 构建source_targets
            source_targets = []
            for st in edge_def.get("source_targets", []):
                source_targets.append(
                    EntityEdgeSourceTarget(
                        source=st.get("source", "Entity"),
                        target=st.get("target", "Entity")
                    )
                )
            
            if source_targets:
                edge_definitions[name] = (edge_class, source_targets)
        
        # 调用Zep API设置本体
        if entity_types or edge_definitions:
            self.client.graph.set_ontology(
                graph_ids=[graph_id],
                entities=entity_types if entity_types else None,
                edges=edge_definitions if edge_definitions else None,
            )
    
    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None
    ) -> List[str]:
        """分批添加文本到图谱，返回所有 episode 的 uuid 列表"""
        episode_uuids = []
        total_chunks = len(chunks)
        
        for i in range(0, total_chunks, batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_chunks + batch_size - 1) // batch_size
            
            if progress_callback:
                progress = (i + len(batch_chunks)) / total_chunks
                progress_callback(
                    t('progress.sendingBatch', current=batch_num, total=total_batches, chunks=len(batch_chunks)),
                    progress
                )
            
            # 构建episode数据
            episodes = [
                EpisodeData(data=chunk, type="text")
                for chunk in batch_chunks
            ]
            
                       # 发送到Zep
            try:
                # --- 手术：注释掉真正的联网请求 ---
                # batch_result = self.client.graph.add_batch(
                #     graph_id=graph_id,
                #     episodes=episodes
                # )
                
                # --- 伪造一个成功的返回结果 ---
                print(f">>> [本地模拟] 已拦截第 {batch_num} 批数据发送，跳过云端提取")
                batch_result = [] 
                # ----------------------------

                
                # 收集返回的 episode uuid
                if batch_result and isinstance(batch_result, list):
                    for ep in batch_result:
                        ep_uuid = getattr(ep, 'uuid_', None) or getattr(ep, 'uuid', None)
                        if ep_uuid:
                            episode_uuids.append(ep_uuid)
                
                # 避免请求过快
                time.sleep(1)
                
            except Exception as e:
                if progress_callback:
                    progress_callback(t('progress.batchFailed', batch=batch_num, error=str(e)), 0)
                raise
        
        return episode_uuids
    
    def _wait_for_episodes(
        self,
        episode_uuids: List[str],
        progress_callback: Optional[Callable] = None,
        timeout: int = 600
    ):
        """等待所有 episode 处理完成"""
        # --- 暴力补丁：直接在这里加一行 return ---
        return 
        # ---------------------------------------
        
        if not episode_uuids:
            # 后面的代码统统都会因为上面的 return 而失效

            if progress_callback:
                progress_callback(t('progress.noEpisodesWait'), 1.0)
            return
        
        start_time = time.time()
        pending_episodes = set(episode_uuids)
        completed_count = 0
        total_episodes = len(episode_uuids)
        
        if progress_callback:
            progress_callback(t('progress.waitingEpisodes', count=total_episodes), 0)
        
        while pending_episodes:
            if time.time() - start_time > timeout:
                if progress_callback:
                    progress_callback(
                        t('progress.episodesTimeout', completed=completed_count, total=total_episodes),
                        completed_count / total_episodes
                    )
                break
            
            # 检查每个 episode 的处理状态
            for ep_uuid in list(pending_episodes):
                try:
                    episode = self.client.graph.episode.get(uuid_=ep_uuid)
                    is_processed = getattr(episode, 'processed', False)
                    
                    if is_processed:
                        pending_episodes.remove(ep_uuid)
                        completed_count += 1
                        
                except Exception as e:
                    # 忽略单个查询错误，继续
                    pass
            
            elapsed = int(time.time() - start_time)
            if progress_callback:
                progress_callback(
                    t('progress.zepProcessing', completed=completed_count, total=total_episodes, pending=len(pending_episodes), elapsed=elapsed),
                    completed_count / total_episodes if total_episodes > 0 else 0
                )
            
            if pending_episodes:
                time.sleep(3)  # 每3秒检查一次
        
        if progress_callback:
            progress_callback(t('progress.processingComplete', completed=completed_count, total=total_episodes), 1.0)
    
    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """【终极补丁】直接返回空信息，彻底切断所有联网请求"""
        print(f">>> 拦截最后的 Zep 统计请求，ID: {graph_id}")
        if not Config.USE_ZEP or graph_id.startswith("local_"):
            graph_data = self.get_local_graph_data(graph_id)
            return GraphInfo(
                graph_id=graph_id,
                node_count=graph_data.get("node_count", 0),
                edge_count=graph_data.get("edge_count", 0),
                entity_types=graph_data.get("entity_types", []),
            )
        return GraphInfo(
            graph_id=graph_id,
            node_count=0,
            edge_count=0,
            entity_types=[]
        )

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """【终极补丁】拦截获取数据请求，防止 10061 报错"""
        print(f">>> 拦截图谱数据请求，ID: {graph_id}")
        if not Config.USE_ZEP or graph_id.startswith("local_"):
            return self.get_local_graph_data(graph_id)
        return {
            "graph_id": graph_id,
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0,
        }

    def delete_graph(self, graph_id: str):
        """【终极补丁】拦截删除请求"""
        print(f">>> 拦截删除请求，ID: {graph_id}")
        pass
