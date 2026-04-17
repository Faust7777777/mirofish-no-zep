"""
OASIS Agent Profile生成器
将Zep图谱中的实体转换为OASIS模拟平台所需的Agent Profile格式

优化改进：
1. 调用Zep检索功能二次丰富节点信息
2. 优化提示词生成非常详细的人设
3. 区分个人实体和抽象群体实体
"""

import json
import random
import time
import csv
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from openai import OpenAI
from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.locale import get_language_instruction, get_locale, set_locale, t
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('mirofish.oasis_profile')


@dataclass
class OasisAgentProfile:
    """OASIS Agent Profile数据结构"""
    # 通用字段
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str
    
    # 可选字段 - Reddit风格
    karma: int = 1000
    
    # 可选字段 - Twitter风格
    friend_count: int = 100
    follower_count: int = 150
    statuses_count: int = 500
    
    # 额外人设信息
    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    interested_topics: List[str] = field(default_factory=list)
    
    # 来源实体信息
    source_entity_uuid: Optional[str] = None
    source_entity_type: Optional[str] = None
    
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    
    def to_reddit_format(self) -> Dict[str, Any]:
        """转换为Reddit平台格式"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS 库要求字段名为 username(无下划线)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at,
        }
        
        # 添加额外人设信息(如果有)
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_twitter_format(self) -> Dict[str, Any]:
        """转换为Twitter平台格式"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS 库要求字段名为 username(无下划线)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "created_at": self.created_at,
        }
        
        # 添加额外人设信息
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为完整字典格式"""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
            "profession": self.profession,
            "interested_topics": self.interested_topics,
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "created_at": self.created_at,
        }


class OasisProfileGenerator:
    """
    OASIS Profile生成器
    
    将Zep图谱中的实体转换为OASIS模拟所需的Agent Profile
    
    优化特性：
    1. 调用Zep图谱检索功能获取更丰富的上下文
    2. 生成非常详细的人设(包括基本信息、职业经历、性格特征、社交媒体行为等)
    3. 区分个人实体和抽象群体实体
    """
    
    # MBTI类型列表
    MBTI_TYPES = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP"
    ]
    
    # 常见国家列表
    COUNTRIES = [
        "China", "US", "UK", "Japan", "Germany", "France", 
        "Canada", "Australia", "Brazil", "India", "South Korea"
    ]
    
    # 个人类型实体(需要生成具体人设)
    INDIVIDUAL_ENTITY_TYPES = [
        "student", "alumni", "professor", "person", "publicfigure", 
        "expert", "faculty", "official", "journalist", "activist"
    ]
    
    # 群体/机构类型实体(需要生成群体代表人设)
    GROUP_ENTITY_TYPES = [
        "university", "governmentagency", "organization", "ngo", 
        "mediaoutlet", "company", "institution", "group", "community"
    ]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        zep_api_key: Optional[str] = None,
        graph_id: Optional[str] = None,
        scene_name: Optional[str] = None,
        scene_description: Optional[str] = None,
        scene_event: Optional[str] = None,
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME

        # 场景上下文（热配置传入）；为空时回退到默认《理想国》设定，保持向后兼容
        self.scene_name = scene_name or "柏拉图《理想国》第三卷——禁诗实验"
        self.scene_description = scene_description or (
            "古希腊雅典城邦内的哲学思想实验：城邦推行严格的诗歌审查制度，禁止描写英雄软弱、恐惧的诗篇。"
        )
        self.scene_event = scene_event or "一首被禁止的诗歌在城邦内悄悄流传，引发各阶层人物的反应与争论。"
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        # Zep客户端用于检索丰富上下文
        self.zep_api_key = zep_api_key or Config.ZEP_API_KEY
        self.zep_client = None
        self.graph_id = graph_id
        
        if self.zep_api_key:
            try:
                self.zep_client = Zep(api_key=self.zep_api_key)
            except Exception as e:
                logger.warning(f"Zep客户端初始化失败: {e}")
    
    def generate_profile_from_entity(
        self,
        entity: EntityNode,
        user_id: int,
        use_llm: bool = True
    ) -> OasisAgentProfile:
        """
        从Zep实体生成OASIS Agent Profile

        Args:
            entity: Zep实体节点
            user_id: 用户ID(用于OASIS)
            use_llm: 是否使用LLM生成详细人设

        Returns:
            OasisAgentProfile
        """
        # EntityNode 的真实类型存放在 labels[0]
        entity_type = (
            getattr(entity, 'entity_type', None)
            or (entity.labels[0] if getattr(entity, 'labels', None) else None)
            or 'Entity'
        )
        
        # 基础信息
        name = entity.name
        user_name = self._generate_username(name)
        
        # 构建上下文信息
        context = self._build_entity_context(entity)
        
        if use_llm:
            # 使用LLM生成详细人设
            profile_data = self._generate_profile_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context
            )
        else:
            # 使用规则生成基础人设
            profile_data = self._generate_profile_rule_based(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes
            )
        
        return OasisAgentProfile(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=profile_data.get("bio", f"{entity_type}: {name}"),
            persona=profile_data.get("persona", entity.summary or f"A {entity_type} named {name}."),
            karma=profile_data.get("karma", random.randint(500, 5000)),
            friend_count=profile_data.get("friend_count", random.randint(50, 500)),
            follower_count=profile_data.get("follower_count", random.randint(100, 1000)),
            statuses_count=profile_data.get("statuses_count", random.randint(100, 2000)),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            mbti=profile_data.get("mbti"),
            country=profile_data.get("country"),
            profession=profile_data.get("profession"),
            interested_topics=profile_data.get("interested_topics", []),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
        )
    
    def _generate_username(self, name: str) -> str:
        """生成用户名"""
        # 移除特殊字符,转换为小写
        username = name.lower().replace(" ", "_")
        username = ''.join(c for c in username if c.isalnum() or c == '_')
        
        # 添加随机后缀避免重复
        suffix = random.randint(100, 999)
        return f"{username}_{suffix}"
    
    def _search_zep_for_entity(self, entity: EntityNode) -> Dict[str, Any]:
        """
        使用Zep图谱混合搜索功能获取实体相关的丰富信息
        
        Zep没有内置混合搜索接口,需要分别搜索edges和nodes然后合并结果。
        使用并行请求同时搜索,提高效率。
        
        Args:
            entity: 实体节点对象
            
        Returns:
            包含facts, node_summaries, context的字典
        """
        import concurrent.futures
        
        if not self.zep_client:
            return {"facts": [], "node_summaries": [], "context": ""}
        
        entity_name = entity.name
        
        results = {
            "facts": [],
            "node_summaries": [],
            "context": ""
        }
        
        # 必须有graph_id才能进行搜索
        if not self.graph_id:
            logger.debug(f"跳过Zep检索：未设置graph_id")
            return results
        
        comprehensive_query = t('progress.zepSearchQuery', name=entity_name)
        
        def search_edges():
            """搜索边(事实/关系)- 带重试机制"""
            max_retries = 3
            last_exception = None
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=30,
                        scope="edges",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"Zep边搜索第 {attempt + 1} 次失败: {str(e)[:80]}, 重试中...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"Zep边搜索在 {max_retries} 次尝试后仍失败: {e}")
            return None
        
        def search_nodes():
            """搜索节点(实体摘要)- 带重试机制"""
            max_retries = 3
            last_exception = None
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=20,
                        scope="nodes",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"Zep节点搜索第 {attempt + 1} 次失败: {str(e)[:80]}, 重试中...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"Zep节点搜索在 {max_retries} 次尝试后仍失败: {e}")
            return None
        
        try:
            # 并行执行edges和nodes搜索
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                edge_future = executor.submit(search_edges)
                node_future = executor.submit(search_nodes)
                
                # 获取结果
                edge_result = edge_future.result(timeout=30)
                node_result = node_future.result(timeout=30)
            
            # 处理边搜索结果
            all_facts = set()
            if edge_result and hasattr(edge_result, 'edges') and edge_result.edges:
                for edge in edge_result.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        all_facts.add(edge.fact)
            results["facts"] = list(all_facts)
            
            # 处理节点搜索结果
            all_summaries = set()
            if node_result and hasattr(node_result, 'nodes') and node_result.nodes:
                for node in node_result.nodes:
                    if hasattr(node, 'summary') and node.summary:
                        all_summaries.add(node.summary)
                    if hasattr(node, 'name') and node.name and node.name != entity_name:
                        all_summaries.add(f"相关实体: {node.name}")
            results["node_summaries"] = list(all_summaries)
            
            # 构建综合上下文
            context_parts = []
            if results["facts"]:
                context_parts.append("事实信息:\n" + "\n".join(f"- {f}" for f in results["facts"][:20]))
            if results["node_summaries"]:
                context_parts.append("相关实体:\n" + "\n".join(f"- {s}" for s in results["node_summaries"][:10]))
            results["context"] = "\n\n".join(context_parts)
            
            logger.info(f"Zep混合检索完成: {entity_name}, 获取 {len(results['facts'])} 条事实, {len(results['node_summaries'])} 个相关节点")
            
        except concurrent.futures.TimeoutError:
            logger.warning(f"Zep检索超时 ({entity_name})")
        except Exception as e:
            logger.warning(f"Zep检索失败 ({entity_name}): {e}")
        
        return results
    
    def _build_entity_context(self, entity: EntityNode) -> str:
        """
        构建实体的完整上下文信息
        
        包括：
        1. 实体本身的边信息(事实)
        2. 关联节点的详细信息
        3. Zep混合检索到的丰富信息
        """
        context_parts = []
        
        # 1. 添加实体属性信息
        if entity.attributes:
            attrs = []
            for key, value in entity.attributes.items():
                if value and str(value).strip():
                    attrs.append(f"- {key}: {value}")
            if attrs:
                context_parts.append("### 实体属性\n" + "\n".join(attrs))
        
        # 2. 添加相关边信息(事实/关系)
        existing_facts = set()
        if entity.related_edges:
            relationships = []
            for edge in entity.related_edges:  # 不限制数量
                fact = edge.get("fact", "")
                edge_name = edge.get("edge_name", "")
                direction = edge.get("direction", "")
                
                if fact:
                    relationships.append(f"- {fact}")
                    existing_facts.add(fact)
                elif edge_name:
                    if direction == "outgoing":
                        relationships.append(f"- {entity.name} --[{edge_name}]--> (相关实体)")
                    else:
                        relationships.append(f"- (相关实体) --[{edge_name}]--> {entity.name}")
            
            if relationships:
                context_parts.append("### 相关事实和关系\n" + "\n".join(relationships))
        
        # 3. 添加关联节点的详细信息
        if entity.related_nodes:
            related_info = []
            for node in entity.related_nodes:  # 不限制数量
                node_name = node.get("name", "")
                node_labels = node.get("labels", [])
                node_summary = node.get("summary", "")
                
                # 过滤掉默认标签
                custom_labels = [l for l in node_labels if l not in ["Entity", "Node"]]
                label_str = f" ({', '.join(custom_labels)})" if custom_labels else ""
                
                if node_summary:
                    related_info.append(f"- **{node_name}**{label_str}: {node_summary}")
                else:
                    related_info.append(f"- **{node_name}**{label_str}")
            
            if related_info:
                context_parts.append("### 关联实体信息\n" + "\n".join(related_info))
        
        # 4. 使用Zep混合检索获取更丰富的信息
        zep_results = self._search_zep_for_entity(entity)
        
        if zep_results.get("facts"):
            # 去重：排除已存在的事实
            new_facts = [f for f in zep_results["facts"] if f not in existing_facts]
            if new_facts:
                context_parts.append("### Zep检索到的事实信息\n" + "\n".join(f"- {f}" for f in new_facts[:15]))
        
        if zep_results.get("node_summaries"):
            context_parts.append("### Zep检索到的相关节点\n" + "\n".join(f"- {s}" for s in zep_results["node_summaries"][:10]))
        
        return "\n\n".join(context_parts)
    
    def _is_individual_entity(self, entity_type: str) -> bool:
        """判断是否是个人类型实体"""
        return entity_type.lower() in self.INDIVIDUAL_ENTITY_TYPES
    
    def _is_group_entity(self, entity_type: str) -> bool:
        """判断是否是群体/机构类型实体"""
        return entity_type.lower() in self.GROUP_ENTITY_TYPES
    
    def _generate_profile_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        使用LLM生成非常详细的人设
        
        根据实体类型区分：
        - 个人实体：生成具体的人物设定
        - 群体/机构实体：生成代表性账号设定
        """
        
        is_individual = self._is_individual_entity(entity_type)
        
        if is_individual:
            prompt = self._build_individual_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        else:
            prompt = self._build_group_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )

        # 尝试多次生成,直到成功或达到最大重试次数
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt(is_individual)},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1)  # 每次重试降低温度
                    # 不设置max_tokens,让LLM自由发挥
                )
                
                content = response.choices[0].message.content
                
                # 检查是否被截断(finish_reason不是'stop')
                finish_reason = response.choices[0].finish_reason
                if finish_reason == 'length':
                    logger.warning(f"LLM输出被截断 (attempt {attempt+1}), 尝试修复...")
                    content = self._fix_truncated_json(content)
                
                # 尝试解析JSON
                try:
                    result = json.loads(content)
                    
                    # 验证必需字段
                    if "bio" not in result or not result["bio"]:
                        result["bio"] = entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"
                    if "persona" not in result or not result["persona"]:
                        result["persona"] = entity_summary or f"{entity_name}是一个{entity_type}。"
                    
                    return result
                    
                except json.JSONDecodeError as je:
                    logger.warning(f"JSON解析失败 (attempt {attempt+1}): {str(je)[:80]}")
                    
                    # 尝试修复JSON
                    result = self._try_fix_json(content, entity_name, entity_type, entity_summary)
                    if result.get("_fixed"):
                        del result["_fixed"]
                        return result
                    
                    last_error = je
                    
            except Exception as e:
                logger.warning(f"LLM调用失败 (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(1 * (attempt + 1))  # 指数退避
        
        logger.warning(f"LLM生成人设失败({max_attempts}次尝试): {last_error}, 使用规则生成")
        return self._generate_profile_rule_based(
            entity_name, entity_type, entity_summary, entity_attributes
        )
    
    def _fix_truncated_json(self, content: str) -> str:
        """修复被截断的JSON(输出被max_tokens限制截断)"""
        import re
        
        # 如果JSON被截断,尝试闭合它
        content = content.strip()
        
        # 计算未闭合的括号
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # 检查是否有未闭合的字符串
        # 简单检查：如果最后一个引号后没有逗号或闭合括号,可能是字符串被截断
        if content and content[-1] not in '",}]':
            # 尝试闭合字符串
            content += '"'
        
        # 闭合括号
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_json(self, content: str, entity_name: str, entity_type: str, entity_summary: str = "") -> Dict[str, Any]:
        """尝试修复损坏的JSON"""
        import re
        
        # 1. 首先尝试修复被截断的情况
        content = self._fix_truncated_json(content)
        
        # 2. 尝试提取JSON部分
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # 3. 处理字符串中的换行符问题
            # 找到所有字符串值并替换其中的换行符
            def fix_string_newlines(match):
                s = match.group(0)
                # 替换字符串内的实际换行符为空格
                s = s.replace('\n', ' ').replace('\r', ' ')
                # 替换多余空格
                s = re.sub(r'\s+', ' ', s)
                return s
            
            # 匹配JSON字符串值
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string_newlines, json_str)
            
            # 4. 尝试解析
            try:
                result = json.loads(json_str)
                result["_fixed"] = True
                return result
            except json.JSONDecodeError as e:
                # 5. 如果还是失败,尝试更激进的修复
                try:
                    # 移除所有控制字符
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                    # 替换所有连续空白
                    json_str = re.sub(r'\s+', ' ', json_str)
                    result = json.loads(json_str)
                    result["_fixed"] = True
                    return result
                except:
                    pass
        
        # 6. 尝试从内容中提取部分信息
        bio_match = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
        persona_match = re.search(r'"persona"\s*:\s*"([^"]*)', content)  # 可能被截断
        
        bio = bio_match.group(1) if bio_match else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}")
        persona = persona_match.group(1) if persona_match else (entity_summary or f"{entity_name}是一个{entity_type}。")
        
        # 如果提取到了有意义的内容,标记为已修复
        if bio_match or persona_match:
            logger.info(f"从损坏的JSON中提取了部分信息")
            return {
                "bio": bio,
                "persona": persona,
                "_fixed": True
            }
        
        # 7. 完全失败,返回基础结构
        logger.warning(f"JSON修复失败,返回基础结构")
        return {
            "bio": entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name}是一个{entity_type}。"
        }
    
    def _get_system_prompt(self, is_individual: bool) -> str:
        """获取系统提示词 - 通用版（场景上下文由 self.scene_* 注入）"""
        base_prompt = (
            f"你是哲学思想实验与社会模拟专家。当前场景是「{self.scene_name}」。"
            f"场景背景：{self.scene_description}\n"
            "你的任务是为该场景生成符合时代背景与立场的角色人设。"
            "【核心要求】：所有人设必须严格贴合场景设定的历史/文化背景，"
            "不要混入与场景不相关的现代元素或异时空设定。"
            "必须返回有效的 JSON，所有字符串值不能包含未转义的换行符。"
        )
        return f"{base_prompt}\n\n{get_language_instruction()}"

    def _build_individual_persona_prompt(self, entity_name, entity_type, entity_summary, entity_attributes, context) -> str:
        """构建个人角色的详细人设提示词 - 通用版"""
        personality = entity_attributes.get("personality", "") if entity_attributes else ""
        group = entity_attributes.get("group", "") if entity_attributes else ""
        return (
            f"为「{self.scene_name}」场景中的个人角色生成详细人设。\n\n"
            f"## 场景设定\n{self.scene_description}\n\n"
            f"## 触发事件\n{self.scene_event}\n\n"
            f"## 角色信息\n"
            f"- 角色名称: {entity_name}\n"
            f"- 角色类型: {entity_type}（所属阶层/群体: {group}）\n"
            f"- 背景简介: {entity_summary}\n"
            f"- 性格关键词: {personality}\n\n"
            f"请生成 JSON，包含以下字段：\n"
            f"1. bio: 该角色的自我介绍，100 字以内，第一人称，口语化，与场景背景一致\n"
            f"2. persona: 详细人设（800 字纯文本，不含换行符），必须涵盖：\n"
            f"   - 此人的具体经历与当前内心状态\n"
            f"   - 他/她对触发事件的本能反应（支持/好奇/愤怒/沉默 等）\n"
            f"   - 说话风格（口语化/迂回/简短/市井 等，需贴合身份）\n"
            f"   - 会主动回应哪类人，会忽视谁\n"
            f"   - 内心真实想法与公开表态之间的差距\n"
            f"3. age: 角色年龄（整数，与场景历史背景吻合）\n"
            f"4. gender: male 或 female\n"
            f"5. mbti: 符合性格的 MBTI 类型\n"
            f"6. country: 与场景设定一致的地点（例如雅典城邦/明朝京师/现代上海 等）\n"
            f"7. profession: 在场景中的具体职责\n"
            f"8. interested_topics: 列表，3-5 个该角色关心的话题关键词\n\n"
            f"重要：persona 必须是连贯的一段文字，不含换行符。{get_language_instruction()}"
        )

    def _build_group_persona_prompt(self, entity_name, entity_type, entity_summary, entity_attributes, context) -> str:
        """构建群体/流派的详细人设提示词 - 通用版"""
        return (
            f"为「{self.scene_name}」场景中的群体/阶层/机构生成详细设定。\n\n"
            f"## 场景设定\n{self.scene_description}\n\n"
            f"## 触发事件\n{self.scene_event}\n\n"
            f"## 群体信息\n"
            f"- 实体名称: {entity_name}\n"
            f"- 实体类型: {entity_type}\n"
            f"- 背景简介: {entity_summary}\n\n"
            "请生成 JSON，包含以下字段：\n"
            "1. bio: 该群体的公认信条/对外表述，200 字以内\n"
            "2. persona: 详细设定描述（2000 字纯文本，单行），需涵盖：\n"
            "   - 群体在场景中的角色、职责与组织方式\n"
            "   - 群体常用的言论风格与话术习惯\n"
            "   - 群体对触发事件的整体立场与利益取向\n"
            "3. age: 固定填 30\n"
            "4. gender: 固定填 \"other\"\n"
            "5. mbti: 用 MBTI 描述该群体的集体性格\n"
            "6. country: 与场景设定一致的地点\n"
            "7. profession: 该群体在场景中的社会分工\n\n"
            "重要要求：\n"
            "- 所有字段值必须是字符串或数字，不要使用换行符\n"
            "- persona 必须是一段连贯的文字\n"
            f"- {get_language_instruction()}（gender 字段必须用英文 male/female/other）\n"
            "- 内容必须与场景背景一致\n"
        )

    def set_graph_id(self, graph_id: str):
        """设置图谱ID用于Zep检索"""
        self.graph_id = graph_id

    def generate_profiles_from_entities(
        self,
        entities: List[EntityNode],
        use_llm: bool = True,
        progress_callback: Optional[callable] = None,
        graph_id: Optional[str] = None,
        parallel_count: int = 3,
        realtime_output_path: Optional[str] = None,
        output_platform: str = "reddit"
    ) -> List[OasisAgentProfile]:
        """
        批量从实体生成Agent Profile (支持并行生成)
        """
        import concurrent.futures
        from threading import Lock
        
        if graph_id:
            self.graph_id = graph_id
        
        total = len(entities)
        profiles = [None] * total
        completed_count = [0]
        lock = Lock()
        
        def save_profiles_realtime():
            if not realtime_output_path:
                return
            with lock:
                existing_profiles = [p for p in profiles if p is not None]
                if not existing_profiles:
                    return
                try:
                    if output_platform == "reddit":
                        profiles_data = [p.to_reddit_format() for p in existing_profiles]
                        with open(realtime_output_path, 'w', encoding='utf-8') as f:
                            json.dump(profiles_data, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.warning(f"实时保存失败: {e}")

        current_locale = get_locale()

        def generate_single_profile(idx: int, entity: EntityNode) -> tuple:
            set_locale(current_locale)
            entity_type = entity.labels[0] if entity.labels else "Entity"
            try:
                profile = self.generate_profile_from_entity(
                    entity=entity,
                    user_id=idx,
                    use_llm=use_llm
                )
                self._print_generated_profile(entity.name, entity_type, profile)
                return idx, profile, None
            except Exception as e:
                logger.error(f"生成 {entity.name} 失败: {str(e)}")
                fallback_profile = OasisAgentProfile(
                    user_id=idx,
                    user_name=self._generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity_type}: {entity.name}",
                    persona=entity.summary or f"「{self.scene_name}」中的参与者。",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity_type,
                    country=self.scene_name,
                )
                return idx, fallback_profile, str(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
            future_to_entity = {
                executor.submit(generate_single_profile, idx, entity): (idx, entity)
                for idx, entity in enumerate(entities)
            }
            for future in concurrent.futures.as_completed(future_to_entity):
                idx, entity = future_to_entity[future]
                try:
                    result_idx, profile, error = future.result()
                    profiles[result_idx] = profile
                    with lock:
                        completed_count[0] += 1
                        current = completed_count[0]
                    save_profiles_realtime()
                    if progress_callback:
                        progress_callback(current, total, f"已完成 {current}/{total}: {entity.name}")
                except Exception as e:
                    logger.error(f"处理 {entity.name} 异常: {str(e)}")

        return profiles

    def _print_generated_profile(self, entity_name: str, entity_type: str, profile: OasisAgentProfile):
        """实时输出生成的人设到控制台"""
        separator = "-" * 70
        topics_str = ', '.join(profile.interested_topics) if profile.interested_topics else '无'
        output = (
            f"\n{separator}\n"
            f"成功生成: {entity_name} ({entity_type})\n"
            f"{separator}\n"
            f"用户名: {profile.user_name}\n"
            f"简介: {profile.bio}\n"
            f"人设详情: {profile.persona[:200]}...\n"
            f"属性: {profile.age}岁 | {profile.gender} | {profile.mbti}\n"
            f"职业: {profile.profession} | 国家: {profile.country}\n"
            f"{separator}\n"
        )
        print(output)

    def save_profiles(self, profiles: List[OasisAgentProfile], file_path: str, platform: str = "reddit"):
        """保存Profile到文件 (重构后的雅典实验版)"""
        if platform == "twitter":
            self._save_twitter_csv(profiles, file_path)
        else:
            self._save_reddit_json(profiles, file_path)

    def _save_twitter_csv(self, profiles: List[OasisAgentProfile], file_path: str):
        """保存Twitter Profile为CSV格式"""
        import csv
        if not profiles: return
        if not file_path.endswith('.csv'):
            file_path = file_path.replace('.json', '.csv')
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['user_id', 'name', 'username', 'user_char', 'description'])
            for idx, p in enumerate(profiles):
                # 合并bio和persona，确保雅典哲学家的人设完整
                user_char = f"{p.bio} {p.persona}".replace('\n', ' ')
                writer.writerow([idx, p.name, p.user_name, user_char, p.bio.replace('\n', ' ')])
        logger.info(f"已成功导出 Twitter CSV 到: {file_path}")

    def _save_reddit_json(self, profiles: List[OasisAgentProfile], file_path: str):
        """保存Reddit Profile为JSON格式"""
        import json
        data = []
        for idx, p in enumerate(profiles):
            data.append({
                "user_id": p.user_id if p.user_id is not None else idx,
                "username": p.user_name,
                "name": p.name,
                "bio": p.bio[:150] if p.bio else p.name,
                "persona": p.persona or f"{p.name} 是「{self.scene_name}」中的参与者。",
                "age": p.age or 30,
                "gender": self._normalize_gender(p.gender),
                "mbti": p.mbti or "INTJ",
                "country": p.country or self.scene_name,
                "profession": p.profession
            })
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"已成功导出 Reddit JSON 到: {file_path}")

    def _normalize_gender(self, gender) -> str:
        """性别标准化映射"""
        g_str = str(gender).strip().lower() if gender else ""
        mapping = {"男": "male", "女": "female", "male": "male", "female": "female"}
        return mapping.get(g_str, "other")
