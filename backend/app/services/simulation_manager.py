import os
import json
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..utils.logger import get_logger
from .zep_entity_reader import ZepEntityReader, EntityNode, FilteredEntities
from .oasis_profile_generator import OasisProfileGenerator
from .simulation_config_generator import SimulationConfigGenerator
from .scene_config_manager import SceneConfigManager, DEFAULT_REPUBLIC_SCENE
from ..utils.locale import t

logger = get_logger('mirofish.simulation')

class SimulationStatus(str, Enum):
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class SimulationState:
    simulation_id: str
    project_id: str
    graph_id: str
    enable_twitter: bool = True
    enable_reddit: bool = True
    status: SimulationStatus = SimulationStatus.CREATED
    entities_count: int = 0
    profiles_count: int = 0
    entity_types: List[str] = field(default_factory=list)
    config_generated: bool = False
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """将状态转换为字典，供前端读取"""
        data = {k: v for k, v in self.__dict__.items()}
        data["status"] = self.status.value
        return data

    # === 把下面这个函数粘贴进去 ===
    def to_simple_dict(self) -> Dict[str, Any]:
        """简单的字典转换，防止任务完成时报错"""
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulationState":
        """从磁盘状态恢复 SimulationState。"""
        raw_status = data.get("status", SimulationStatus.CREATED.value)
        try:
            status = raw_status if isinstance(raw_status, SimulationStatus) else SimulationStatus(raw_status)
        except ValueError:
            logger.warning(f"未知模拟状态 {raw_status}，回退为 created")
            status = SimulationStatus.CREATED

        return cls(
            simulation_id=data["simulation_id"],
            project_id=data["project_id"],
            graph_id=data["graph_id"],
            enable_twitter=data.get("enable_twitter", True),
            enable_reddit=data.get("enable_reddit", True),
            status=status,
            entities_count=data.get("entities_count", 0),
            profiles_count=data.get("profiles_count", 0),
            entity_types=data.get("entity_types", []),
            config_generated=data.get("config_generated", False),
            error=data.get("error"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )

class SimulationManager:
    """
    理想国定制版模拟管理器
    完全拦截云端 Zep 请求，强制注入 17 位城邦居民。
    """
    SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../../uploads/simulations')
    
    def __init__(self):
        os.makedirs(self.SIMULATION_DATA_DIR, exist_ok=True)
        # 内存缓存，重启 run.py 会清空，所以每次重启都要刷新网页重开模拟
        self._simulations: Dict[str, SimulationState] = {}

    def _get_simulation_dir(self, simulation_id: str) -> str:
        sim_dir = os.path.join(self.SIMULATION_DATA_DIR, simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        return sim_dir

    def _get_simulation_dir_path(self, simulation_id: str) -> str:
        return os.path.join(self.SIMULATION_DATA_DIR, simulation_id)

    def _get_state_path(self, simulation_id: str) -> str:
        return os.path.join(self._get_simulation_dir_path(simulation_id), "state.json")

    def _save_simulation_state(self, state: SimulationState):
        sim_dir = self._get_simulation_dir(state.simulation_id)
        state.updated_at = datetime.now().isoformat()
        with open(os.path.join(sim_dir, "state.json"), 'w', encoding='utf-8') as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        self._simulations[state.simulation_id] = state

    def _load_simulation_state(self, simulation_id: str) -> Optional[SimulationState]:
        state_path = self._get_state_path(simulation_id)
        if not os.path.exists(state_path):
            return None

        try:
            with open(state_path, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            state = SimulationState.from_dict(state_data)
            self._simulations[simulation_id] = state
            return state
        except Exception as e:
            logger.warning(f"加载模拟状态失败: simulation_id={simulation_id}, error={e}")
            return None

    def create_simulation(self, project_id: str, graph_id: str, enable_twitter: bool = True, enable_reddit: bool = True, **kwargs) -> SimulationState:
        """创建模拟条目"""
        sim_id = f"sim_{uuid.uuid4().hex[:12]}"
        state = SimulationState(
            simulation_id=sim_id, 
            project_id=project_id, 
            graph_id=graph_id,
            enable_twitter=enable_twitter,
            enable_reddit=enable_reddit
        )
        self._save_simulation_state(state)
        print(f">>> [创建] 模拟任务已就绪: {sim_id}")
        return state

    def prepare_simulation(
        self,
        simulation_id: str,
        simulation_requirement: str = "",
        document_text: str = "",
        defined_entity_types: Optional[List[str]] = None,
        use_llm_for_profiles: bool = True,
        progress_callback: Optional[Any] = None,
        parallel_profile_count: int = 3,
        scene_config_name: Optional[str] = None,
        **kwargs
    ) -> Optional[SimulationState]:
        """核心函数：对齐前端参数，执行灵魂注入

        新参数 scene_config_name：从场景配置文件加载角色 + 初始帖子。
        缺省时回退到默认《理想国》17 人，保持向后兼容。
        """
        state = self.get_simulation(simulation_id)
        if not state:
            print(f">>> [错误] 404 - 找不到模拟任务: {simulation_id}。请刷新网页重试。")
            return None

        try:
            state.status = SimulationStatus.PREPARING
            self._save_simulation_state(state)
            sim_dir = self._get_simulation_dir(simulation_id)

            # 1. 加载场景配置：优先用前端选中的场景，其次用默认《理想国》场景
            scene_config = None
            if scene_config_name:
                try:
                    scene_config = SceneConfigManager.get_scene(scene_config_name)
                    if scene_config:
                        print(f">>> [场景] 已加载热配置场景: {scene_config_name}")
                except Exception as e:
                    print(f">>> [场景] 读取热配置失败，回退到默认场景: {e}")

            if not scene_config:
                scene_config = DEFAULT_REPUBLIC_SCENE
                print(">>> [场景] 使用默认《理想国》场景")

            raw_actors = scene_config.get("actors") or DEFAULT_REPUBLIC_SCENE["actors"]
            scene_initial_posts = scene_config.get("initial_posts") or []
            scene_name = scene_config.get("scene_name") or DEFAULT_REPUBLIC_SCENE["scene_name"]
            scene_description = scene_config.get("scene_description") or ""
            scene_event = scene_config.get("scene_event") or ""

            if progress_callback:
                progress_callback("reading", 10, f"正在加载场景：{scene_name}")

            entities = [EntityNode(
                uuid=f"actor_{i}",
                name=a["name"],
                labels=[a["label"]],
                summary=a.get("summary", ""),
                attributes={
                    "personality": a.get("personality", ""),
                    "group": a["label"],
                },
            ) for i, a in enumerate(raw_actors)]

            state.entities_count = len(entities)
            state.entity_types = list({a["label"] for a in raw_actors})

            # 2. 生成人设（场景信息会注入到 prompt 模板）
            if progress_callback:
                progress_callback("generating_profiles", 30, "正在塑造角色人设...")
            generator = OasisProfileGenerator(
                graph_id=state.graph_id,
                scene_name=scene_name,
                scene_description=scene_description,
                scene_event=scene_event,
            )
            profiles = generator.generate_profiles_from_entities(
                entities=entities, use_llm=use_llm_for_profiles
            )

            # 同时保存 Reddit 和 Twitter，确保前端不报错
            generator.save_profiles(profiles, os.path.join(sim_dir, "reddit_profiles.json"), "reddit")
            generator.save_profiles(profiles, os.path.join(sim_dir, "twitter_profiles.csv"), "twitter")
            state.profiles_count = len(profiles)

            # 3. 生成模拟配置
            if progress_callback:
                progress_callback("generating_config", 80, "正在生成模拟参数...")
            # simulation_requirement 兜底：场景描述 / 触发事件
            effective_requirement = (
                simulation_requirement.strip()
                or f"{scene_name}\n场景：{scene_description}\n触发事件：{scene_event}"
            )
            config_gen = SimulationConfigGenerator()
            sim_params = config_gen.generate_config(
                simulation_id=simulation_id,
                project_id=state.project_id,
                graph_id=state.graph_id,
                simulation_requirement=effective_requirement,
                document_text=document_text,
                entities=entities,
                enable_twitter=state.enable_twitter,
                enable_reddit=state.enable_reddit,
            )

            # 4. 把场景配置里的 initial_posts 合并到 event_config
            #    并按 poster_type 分配给同 label 的 agent
            if scene_initial_posts:
                merged_posts = self._merge_scene_initial_posts(
                    scene_initial_posts, sim_params.agent_configs
                )
                if merged_posts:
                    # 覆盖：场景配置里的初始帖子是用户显式指定的，优先级高于 LLM 生成
                    sim_params.event_config.initial_posts = merged_posts

            with open(os.path.join(sim_dir, "simulation_config.json"), 'w', encoding='utf-8') as f:
                f.write(sim_params.to_json())

            # 把场景元数据也写入模拟目录，方便后续查询
            with open(os.path.join(sim_dir, "scene_config.json"), 'w', encoding='utf-8') as f:
                json.dump(scene_config, f, ensure_ascii=False, indent=2)

            state.config_generated = True
            state.status = SimulationStatus.READY
            self._save_simulation_state(state)
            if progress_callback:
                progress_callback("complete", 100, f"{scene_name} 已准备就绪！")
            print(f">>> [成功] {len(entities)} 位角色已在广场就位（场景：{scene_name}）。")
            return state
            
        except Exception as e:
            print(f">>> [失败] 准备出错: {str(e)}")
            import traceback
            traceback.print_exc()
            state.status = SimulationStatus.FAILED
            state.error = str(e)
            self._save_simulation_state(state)
            return state
        
    def get_run_instructions(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """获取模拟运行指令"""
        state = self.get_simulation(simulation_id)
        if not state:
            return None
        
        sim_dir = self._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            return None
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        return {
            "simulation_id": simulation_id,
            "status": state.status.value,
            "config": config
        }    
    
    def get_simulation_config(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """获取模拟配置"""
        sim_dir = self._get_simulation_dir_path(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            return None
            
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def update_agent_sentiment_bias(
        self,
        simulation_id: str,
        agent_id: int,
        sentiment_bias: float
    ) -> Dict[str, Any]:
        """更新模拟配置中单个 Agent 的情感倾向。"""
        sim_dir = self._get_simulation_dir_path(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")

        if not os.path.exists(config_path):
            raise ValueError("模拟配置不存在")

        normalized_bias = max(-1.0, min(1.0, float(sentiment_bias)))

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        agent_configs = config.get("agent_configs", [])
        target_agent = None
        for agent in agent_configs:
            if int(agent.get("agent_id", -1)) == int(agent_id):
                agent["sentiment_bias"] = round(normalized_bias, 2)
                target_agent = agent
                break

        if not target_agent:
            raise ValueError(f"未找到 Agent {agent_id}")

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        return {
            "agent": target_agent,
            "config": config
        }

    def get_simulation(self, simulation_id: str) -> Optional[SimulationState]:
        """获取状态存根"""
        state = self._simulations.get(simulation_id)
        if state:
            return state
        return self._load_simulation_state(simulation_id)

    def list_simulations(self) -> List[SimulationState]:
        """列出所有可恢复的模拟（按创建时间倒序）。"""
        simulation_ids = set(self._simulations.keys())

        try:
            for item in os.listdir(self.SIMULATION_DATA_DIR):
                if os.path.isdir(os.path.join(self.SIMULATION_DATA_DIR, item)):
                    simulation_ids.add(item)
        except FileNotFoundError:
            return []

        sims = []
        for simulation_id in simulation_ids:
            state = self.get_simulation(simulation_id)
            if state:
                sims.append(state)

        sims.sort(key=lambda s: s.created_at, reverse=True)
        return sims

    @staticmethod
    def _merge_scene_initial_posts(
        scene_initial_posts: List[Dict[str, Any]],
        agent_configs: List[Any],
    ) -> List[Dict[str, Any]]:
        """
        把场景配置里的 initial_posts 转换为 event_config.initial_posts 的格式
        （每条带 poster_agent_id），按 poster_type==entity_type 匹配第一个可用 agent。
        """
        if not agent_configs:
            return []

        # 按 entity_type 索引 agent
        agents_by_type: Dict[str, List[Any]] = {}
        for ac in agent_configs:
            etype = (ac.entity_type or "").lower()
            agents_by_type.setdefault(etype, []).append(ac)

        used_idx: Dict[str, int] = {}
        merged = []
        for post in scene_initial_posts:
            poster_type_raw = (post.get("poster_type") or "").strip()
            poster_type = poster_type_raw.lower()
            content = post.get("content", "")
            platform = (post.get("platform") or "both").lower()

            matched_agent_id = None
            if poster_type and poster_type in agents_by_type:
                pool = agents_by_type[poster_type]
                idx = used_idx.get(poster_type, 0) % len(pool)
                matched_agent_id = pool[idx].agent_id
                used_idx[poster_type] = idx + 1
            else:
                # 找不到匹配类型，回退到第一个 agent
                matched_agent_id = agent_configs[0].agent_id

            merged.append({
                "content": content,
                "poster_type": poster_type_raw or "Unknown",
                "poster_agent_id": matched_agent_id,
                "platform": platform,
            })
        return merged
