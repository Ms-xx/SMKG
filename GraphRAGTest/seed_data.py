"""
初始化知识图谱的示例数据
包含关于钙钛矿太阳能电池领域的实体和关系
"""
from neo4j_client import neo4j_client
from loguru import logger
import asyncio


# 示例数据：钙钛矿太阳能电池研究领域
SEED_NODES = [
    # 材料类
    {
        "label": "Material",
        "id": "MAPbI3",
        "properties": {
            "name": "MAPbI₃",
            "full_name": "甲基铵碘化铅",
            "formula": "CH₃NH₃PbI₃",
            "description": "最常用的钙钛矿吸光材料，带隙约1.55eV"
        }
    },
    {
        "label": "Material",
        "id": "FAPbI3",
        "properties": {
            "name": "FAPbI₃",
            "full_name": "甲脒碘化铅",
            "formula": "HC(NH₂)₂PbI₃",
            "description": "具有更窄带隙(~1.45eV)的钙钛矿材料"
        }
    },
    {
        "label": "Material",
        "id": "Spiro-OMeTAD",
        "properties": {
            "name": "Spiro-OMeTAD",
            "full_name": "2,2',7,7'-四[N,N-二(4-甲氧基苯基)氨基]-9,9'-螺二芴",
            "formula": "C81H68N4O8",
            "description": "常用的空穴传输材料"
        }
    },
    {
        "label": "Material",
        "id": "TiO2",
        "properties": {
            "name": "TiO₂",
            "full_name": "二氧化钛",
            "formula": "TiO₂",
            "description": "电子传输层材料，常见于介孔结构"
        }
    },
    {
        "label": "Material",
        "id": "PCBM",
        "properties": {
            "name": "PCBM",
            "full_name": "[6,6]-苯基-C61-丁酸甲酯",
            "formula": "C72H14O2",
            "description": "富勒烯衍生物，电子传输材料"
        }
    },

    # 性能类
    {
        "label": "Property",
        "id": "high_efficiency",
        "properties": {
            "name": "高效率",
            "value": "25.7%",
            "description": "单结钙钛矿太阳能电池最高认证效率"
        }
    },
    {
        "label": "Property",
        "id": "good_stability",
        "properties": {
            "name": "稳定性",
            "description": "钙钛矿材料在环境条件下的稳定性"
        }
    },
    {
        "label": "Property",
        "id": "broad_absorption",
        "properties": {
            "name": "宽光谱吸收",
            "description": "钙钛矿材料广谱吸收特性，覆盖可见光区域"
        }
    },

    # 方法类
    {
        "label": "Method",
        "id": "anti_solvent_method",
        "properties": {
            "name": "反溶剂法",
            "full_name": "反溶剂结晶法",
            "description": "通过反溶剂诱导钙钛矿结晶的薄膜制备方法"
        }
    },
    {
        "label": "Method",
        "id": "vacuum_deposition",
        "properties": {
            "name": "真空蒸镀法",
            "description": "在真空条件下通过物理气相沉积制备薄膜"
        }
    },
]

# 关系数据
SEED_RELATIONS = [
    {
        "source_label": "Material",
        "source_id": "MAPbI3",
        "target_label": "Property",
        "target_id": "high_efficiency",
        "rel_type": "ACHIEVES",
        "properties": {
            "context": "MAPbI₃钙钛矿电池实现了超过25%的光电转换效率"
        }
    },
    {
        "source_label": "Material",
        "source_id": "MAPbI3",
        "target_label": "Property",
        "target_id": "good_stability",
        "rel_type": "HAS_CHALLENGE",
        "properties": {
            "context": "MAPbI₃对水分和热量敏感，稳定性有待提升"
        }
    },
    {
        "source_label": "Material",
        "source_id": "FAPbI3",
        "target_label": "Property",
        "target_id": "high_efficiency",
        "rel_type": "ACHIEVES",
        "properties": {
            "context": "FAPbI₃基电池效率可达26%"
        }
    },
    {
        "source_label": "Material",
        "source_id": "MAPbI3",
        "target_label": "Property",
        "target_id": "broad_absorption",
        "rel_type": "EXHIBITS",
        "properties": {
            "context": "MAPbI₃吸收光谱范围400-800nm"
        }
    },
    {
        "source_label": "Method",
        "source_id": "anti_solvent_method",
        "target_label": "Material",
        "target_id": "MAPbI3",
        "rel_type": "PRODUCES",
        "properties": {
            "context": "反溶剂法可制备高质量MAPbI₃薄膜"
        }
    },
    {
        "source_label": "Method",
        "source_id": "vacuum_deposition",
        "target_label": "Material",
        "target_id": "FAPbI3",
        "rel_type": "PRODUCES",
        "properties": {
            "context": "真空蒸镀可精确控制FAPbI₃薄膜厚度"
        }
    },
    {
        "source_label": "Material",
        "source_id": "Spiro-OMeTAD",
        "target_label": "Material",
        "target_id": "MAPbI3",
        "rel_type": "TRANSPORTS_HOLE",
        "properties": {
            "context": "Spiro-OMeTAD作为空穴传输层与MAPbI₃配合使用"
        }
    },
    {
        "source_label": "Material",
        "source_id": "TiO2",
        "target_label": "Material",
        "target_id": "MAPbI3",
        "rel_type": "TRANSPORTS_ELECTRON",
        "properties": {
            "context": "TiO₂电子传输层提取MAPbI₃的光生电子"
        }
    },
    {
        "source_label": "Material",
        "source_id": "PCBM",
        "target_label": "Material",
        "target_id": "FAPbI3",
        "rel_type": "TRANSPORTS_ELECTRON",
        "properties": {
            "context": "PCBM作为电子传输层用于FAPbI₃器件"
        }
    },
    {
        "source_label": "Property",
        "source_id": "high_efficiency",
        "target_label": "Property",
        "target_id": "good_stability",
        "rel_type": "REQUIRES",
        "properties": {
            "context": "高效率钙钛矿电池需要同时具备良好的稳定性"
        }
    },
]


async def seed_data():
    """初始化示例数据到 Neo4j"""
    logger.info("开始初始化知识图谱示例数据...")

    # 创建节点
    created_nodes = 0
    for node_data in SEED_NODES:
        try:
            result = await neo4j_client.create_or_update_node(
                label=node_data["label"],
                match_key="id",
                match_value=node_data["id"],
                properties=node_data["properties"],
            )
            created_nodes += 1
            logger.info(f"  ✓ 创建节点: [{node_data['label']}] {node_data['id']}")
        except Exception as e:
            logger.error(f"  ✗ 创建节点失败: {node_data['id']} - {e}")

    logger.info(f"节点创建完成: {created_nodes}/{len(SEED_NODES)}")

    # 创建关系
    created_relations = 0
    for rel_data in SEED_RELATIONS:
        try:
            result = await neo4j_client.create_relation(
                source_label=rel_data["source_label"],
                source_key="id",
                source_value=rel_data["source_id"],
                target_label=rel_data["target_label"],
                target_key="id",
                target_value=rel_data["target_id"],
                rel_type=rel_data["rel_type"],
                properties=rel_data.get("properties"),
            )
            created_relations += 1
            logger.info(f"  ✓ 创建关系: {rel_data['source_id']} --[{rel_data['rel_type']}]--> {rel_data['target_id']}")
        except Exception as e:
            logger.error(f"  ✗ 创建关系失败: {rel_data['source_id']} -> {rel_data['target_id']} - {e}")

    logger.info(f"关系创建完成: {created_relations}/{len(SEED_RELATIONS)}")

    # 输出统计
    stats = await neo4j_client.get_stats()
    logger.info(f"图谱统计: {stats}")

    return {
        "nodes_created": created_nodes,
        "relations_created": created_relations,
        "total_nodes": stats.get("total_nodes", 0),
        "total_relations": stats.get("total_relations", 0),
    }


if __name__ == "__main__":
    result = asyncio.run(seed_data())
    print(f"\n初始化完成: {result}")
