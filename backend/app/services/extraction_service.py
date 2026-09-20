"""
信息抽取服务
实现基于LLM和NER模型的实体、关系抽取功能
"""

import re
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document, DocumentElement, DocumentPage


class ExtractionService:
    """信息抽取服务,负责从解析后的文档中提取实体、关系和知识"""

    def __init__(self):
        # 这里可以加载NER模型、LLM等
        # 实际应用中应该从配置中加载模型路径
        self.entity_types = {
            "Material": ["钙钛矿", "材料", "化合物", "聚合物"],
            "Property": ["效率", "性能", "稳定性", "带隙"],
            "Method": ["方法", "制备", "合成", "表征"],
            "Parameter": ["温度", "时间", "浓度", "压力"],
            "Result": ["数值", "百分比", "百分比"],
        }

    async def extract_entities(self, text: str, model: str = "default") -> List[Dict]:
        """
        从文本中提取实体：NER（SciBERT 微调 token classification）优先，规则作为回退/召回补充。
        Args:
            text: 待抽取的文本
            model: 使用的模型类型
        Returns:
            实体列表,每个实体包含text, type, start, end等信息
        """
        entities: List[Dict] = []

        # 1) 简化的规则匹配（回退路径，保证无模型时可用）
        for entity_type, keywords in self.entity_types.items():
            for keyword in keywords:
                # 使用正则表达式查找关键词
                pattern = re.compile(keyword, re.IGNORECASE)
                for match in pattern.finditer(text):
                    entity = {
                        "text": match.group(),
                        "type": entity_type,
                        "start": match.start(),
                        "end": match.end(),
                        "confidence": 0.75,  # 简化的置信度
                    }
                    entities.append(entity)

        # 2) NER 增强（模型可用时其结果优先，与规则结果按位置去重合并）
        ner_entities = self._extract_by_ner(text)
        merged: Dict[tuple, Dict] = {}
        for e in entities:
            merged[(e["start"], e["text"].lower())] = e
        for e in ner_entities:
            merged[(e["start"], e["text"].lower())] = e

        # 去重和排序
        return sorted(merged.values(), key=lambda x: x["start"])

    def _extract_by_ner(self, text: str) -> List[Dict]:
        """调用 SciBERT NER（模型缺失时返回空列表，由调用方回退到规则/LLM）。"""
        if not settings.NER_ENABLED:
            return []
        from app.services.ner_service import ner_service

        return ner_service.extract(text)

    async def extract_relations(self, text: str, entities: List[Dict]) -> List[Dict]:
        """
        从文本中提取实体之间的关系
        Args:
            text: 原文本
            entities: 已提取的实体列表
        Returns:
            关系列表
        """
        relations = []

        # 简化的关系抽取方法
        # 实际应用中应该使用关系抽取模型或LLM
        relation_patterns = [
            {
                "pattern": r"(.+?)具有(.+?)性能",
                "relation_type": "HAS_PROPERTY",
            },
            {
                "pattern": r"(.+?)由(.+?)制备",
                "relation_type": "PRODUCED_BY",
            },
            {
                "pattern": r"(.+?)改善(.+?)",
                "relation_type": "IMPROVES",
            },
            {
                "pattern": r"(.+?)相关于(.+?)",
                "relation_type": "CORRELATES_WITH",
            },
        ]

        for pattern_info in relation_patterns:
            pattern = re.compile(pattern_info["pattern"])
            matches = pattern.finditer(text)

            for match in matches:
                # 查找匹配中涉及的实体
                source_text = match.group(1)
                target_text = match.group(2) if len(match.groups()) > 1 else None

                if target_text:
                    # 在实体列表中查找对应的实体
                    source_entity = self._find_entity_by_text(entities, source_text)
                    target_entity = self._find_entity_by_text(entities, target_text)

                    if source_entity and target_entity:
                        relation = {
                            "source": source_entity["text"],
                            "source_type": source_entity["type"],
                            "target": target_entity["text"],
                            "target_type": target_entity["type"],
                            "relation_type": pattern_info["relation_type"],
                            "confidence": 0.7,
                            "context": match.group(0),
                        }
                        relations.append(relation)

        # 2) REBEL 关系抽取增强（模型可用时补充，输出与 NER 实体对齐）
        rebel_relations = self._extract_relations_by_rebel(text, entities)

        # 3) 去重合并（按 source/target/relation_type 去重，REBEL 补充规则遗漏的三元组）
        merged: Dict[tuple, Dict] = {}
        for r in relations + rebel_relations:
            merged[(r["source"], r["target"], r["relation_type"])] = r
        return list(merged.values())

    def _extract_relations_by_rebel(self, text: str, entities: List[Dict]) -> List[Dict]:
        """调用 REBEL 关系抽取（模型缺失时返回空列表，由规则/LLM 兜底）。"""
        if not settings.RELATION_EXTRACTION_ENABLED:
            return []
        from app.services.rebel_service import rebel_service

        return rebel_service.extract(text, entities)

    def _find_entity_by_text(self, entities: List[Dict], text: str) -> Optional[Dict]:
        """根据文本查找实体"""
        for entity in entities:
            if entity["text"] == text or text in entity["text"]:
                return entity
        return None

    async def process_document(self, document_id: str, db: AsyncSession) -> Dict:
        """
        处理整个文档,提取所有实体和关系
        Args:
            document_id: 文档ID
            db: 数据库会话
        Returns:
            处理结果
        """
        # 获取文档
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()

        if not document:
            raise ValueError(f"Document {document_id} not found")

        # 获取文档的所有元素
        elements_result = await db.execute(
            select(DocumentElement).where(
                DocumentElement.page_id.in_(
                    select(DocumentPage.id).where(DocumentPage.document_id == document_id)
                )
            )
        )
        elements = elements_result.scalars().all()

        all_entities = []
        all_relations = []

        # 处理每个文本元素
        for element in elements:
            if element.element_type in ("text", "paragraph", "title", "list") and element.content:
                entities = await self.extract_entities(element.content)
                relations = await self.extract_relations(element.content, entities)

                # 保存实体和关系信息到元素的metadata
                element.metadata = {
                    "entities": entities,
                    "relations": relations,
                }

                all_entities.extend(entities)
                all_relations.extend(relations)

        await db.flush()

        return {
            "document_id": document_id,
            "total_entities": len(all_entities),
            "total_relations": len(all_relations),
            "entities": all_entities,
            "relations": all_relations,
        }

    async def extract_with_llm(self, text: str, prompt_template: str = None) -> Dict:
        """
        使用LLM进行更精确的信息抽取
        Args:
            text: 待抽取文本
            prompt_template: 提示模板
        Returns:
            抽取结果
        """
        # 这里应该集成实际的LLM调用
        # 目前返回占位结果
        if prompt_template is None:
            prompt_template = """
            请从以下科学文献文本中提取:
            1. 材料实体(材料名称、化学式)
            2. 性能指标(数值、单位)
            3. 方法(制备方法、表征技术)
            4. 参数(实验参数)
            5. 关系(材料-性能、方法-效果等关系)

            文本: {text}

            请以JSON格式返回结果。
            """

        # 实际应用中应该调用LLM API或本地模型
        # response = await self._call_llm(prompt_template.format(text=text))

        return {
            "entities": [],
            "relations": [],
            "confidence": 0.85,
        }

    async def _call_llm(self, prompt: str) -> str:
        """
        调用LLM API或本地模型
        Args:
            prompt: 提示文本
        Returns:
            LLM响应
        """
        # 这里应该实现实际的LLM调用逻辑
        # 可以使用transformers、OpenAI API等
        pass
