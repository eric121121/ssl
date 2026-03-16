# -*- coding: utf-8 -*-
"""
把论文仿真章节的三套节点数据写入数据库，生成方案“论文方案”等。

运行方式：
    python3 lunwendata.py
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Sequence

from pymysql.err import IntegrityError
from config import DATABASE_CONFIG, NODE_TYPES
from repositories.mysql_repository import MySQLRepository
from services.node_service import NodeService

CREATOR = "仿真数据导入"
DEFAULT_PARALLEL_LIMIT = 1
DEFAULT_COMMAND_CAPACITY = 3

TARGETS: List[Dict[str, Any]] = [
    {
        "node_name": "敌方目标",
        "target_type": "地面目标",
        "threat_level": 1,
        "x": 0.0,
        "y": 35.0,
        "h": 0.0,
        "vx": 0.0,
        "vy": 0.0,
        "vh": 0.0,
    }
]


def recon_node(node_name: str, x: float, y: float, recon_range: float, processing_time: float, recon_precision: float) -> Dict[str, Any]:
    return {
        "node_name": node_name,
        "model": "侦察",
        "parallel_limit": DEFAULT_PARALLEL_LIMIT,
        "recon_range": recon_range,
        "recon_precision": recon_precision,
        "processing_time": processing_time,
        "x": x,
        "y": y,
        "h": 0.0,
        "vx": 0.0,
        "vy": 0.0,
        "vh": 0.0,
    }


def command_node(
    node_name: str, x: float, y: float, comm_distance: float, processing_time: float, command_capacity: int = DEFAULT_COMMAND_CAPACITY
) -> Dict[str, Any]:
    return {
        "node_name": node_name,
        "command_capacity": command_capacity,
        "comm_distance": comm_distance,
        "processing_time": processing_time,
        "x": x,
        "y": y,
        "h": 0.0,
        "vx": 0.0,
        "vy": 0.0,
        "vh": 0.0,
    }


def fire_node(
    node_name: str, x: float, y: float, comm_distance: float, processing_time: float, ammo_type: str, firepower_type: Optional[str] = None
) -> Dict[str, Any]:
    return {
        "node_name": node_name,
        "firepower_type": firepower_type or ammo_type,
        "ammo_type": ammo_type,
        "comm_distance": comm_distance,
        "processing_time": processing_time,
        "x": x,
        "y": y,
        "h": 0.0,
        "vx": 0.0,
        "vy": 0.0,
        "vh": 0.0,
    }


def ammo_payload(
    ammo_type: str,
    precision_value: float,
    max_range: float,
    flight_time: float,
    ammo_count: int = 12,
    conversion_coeff: float = 1.0,
    damage_radius: float = 0.0,
    cost: float = 0.0,
) -> Dict[str, Any]:
    return {
        "ammo_type": ammo_type,
        "precision_value": precision_value,
        "ammo_count": ammo_count,
        "max_range": max_range,
        "damage_radius": damage_radius,
        "conversion_coeff": conversion_coeff,
        "flight_time": flight_time,
        "cost": cost,
    }


# ---- 仿真章节节点数据（方案一 / 二 / 三） ----
RECON_SCHEME_ONE: List[Dict[str, Any]] = [
    recon_node("R1", -5.0, 34.0, 6.0, 5.0, 1.0),
    recon_node("R2", -6.0, 36.0, 5.0, 7.0, 1.5),
    recon_node("R3", -4.0, 37.0, 5.0, 6.0, 1.2),
    recon_node("R4", -5.0, 33.0, 7.0, 8.0, 1.8),
]

RECON_SCHEME_TWO_EXTRA: List[Dict[str, Any]] = [
    recon_node("R5", -7.0, 36.0, 8.0, 7.0, 1.3),
    recon_node("R6", -6.0, 34.0, 7.0, 6.0, 1.4),
    recon_node("R7", -4.0, 32.0, 5.0, 5.5, 1.6),
    recon_node("R8", -3.0, 38.0, 5.0, 6.5, 1.7),
]

RECON_SCHEME_THREE_EXTRA: List[Dict[str, Any]] = [
    recon_node("R9", -8.0, 38.0, 9.0, 7.5, 1.3),
    recon_node("R10", -9.0, 34.0, 10.0, 7.0, 1.6),
    recon_node("R11", -7.0, 32.0, 8.0, 6.5, 1.9),
    recon_node("R12", -6.0, 30.0, 8.0, 6.8, 2.1),
]

COMMAND_SCHEME_ONE: List[Dict[str, Any]] = [
    command_node("C1", -10.0, 37.0, 6.0, 4.0),
    command_node("C2", -10.0, 31.0, 5.5, 3.5),
]

COMMAND_SCHEME_TWO_EXTRA: List[Dict[str, Any]] = [
    command_node("C3", -12.0, 36.0, 6.5, 4.5),
    command_node("C4", -11.0, 33.0, 6.0, 4.0),
]

COMMAND_SCHEME_THREE_EXTRA: List[Dict[str, Any]] = [
    command_node("C5", -13.0, 35.0, 7.0, 5.0),
    command_node("C6", -12.0, 32.0, 7.0, 4.5),
]

FIRE_SCHEME_ONE: List[Dict[str, Any]] = [
    fire_node("F1", -15.0, 36.0, 18.0, 15.0, "火箭弹"),
    fire_node("F2", -15.0, 35.0, 60.0, 15.0, "巡飞弹"),
    fire_node("F3", -14.0, 32.0, 15.0, 3.0, "122榴弹炮"),
    fire_node("F4", -13.0, 38.0, 2.5, 8.0, "坦克炮"),
    fire_node("F5", -14.0, 30.0, 16.0, 12.0, "红箭-10"),
]

FIRE_SCHEME_TWO_EXTRA: List[Dict[str, Any]] = [
    fire_node("远程火箭炮-加强型", -16.0, 34.0, 20.0, 10.0, "远程火箭炮-加强型"),
    fire_node("制导火箭弹", -12.0, 35.0, 25.0, 6.0, "制导火箭弹"),
    fire_node("远程巡飞弹", -17.0, 37.0, 30.0, 14.0, "远程巡飞弹"),
]

FIRE_SCHEME_THREE_EXTRA: List[Dict[str, Any]] = [
    fire_node("战术导弹", -18.0, 34.0, 35.0, 16.0, "战术导弹"),
    fire_node("区域防空导弹", -16.0, 38.0, 25.0, 11.0, "区域防空导弹"),
    fire_node("反舰导弹", -17.0, 32.0, 28.0, 9.0, "反舰导弹"),
    fire_node("战术巡航导弹", -19.0, 36.0, 40.0, 18.0, "战术巡航导弹"),
]

SCHEMES: List[Dict[str, Any]] = [
    {
        "scheme_name": "论文方案",
        "description": "方案一：小规模验证场景",
        "targets": TARGETS,
        "recon": RECON_SCHEME_ONE,
        "command": COMMAND_SCHEME_ONE,
        "fire": FIRE_SCHEME_ONE,
    },
    {
        "scheme_name": "方案二：中等规模对比场景",
        "description": "方案二：中等规模对比场景",
        "targets": TARGETS,
        "recon": RECON_SCHEME_ONE + RECON_SCHEME_TWO_EXTRA,
        "command": COMMAND_SCHEME_ONE + COMMAND_SCHEME_TWO_EXTRA,
        "fire": FIRE_SCHEME_ONE + FIRE_SCHEME_TWO_EXTRA,
    },
    {
        "scheme_name": "方案三：大规模应用场景",
        "description": "方案三：大规模应用场景",
        "targets": TARGETS,
        "recon": RECON_SCHEME_ONE + RECON_SCHEME_TWO_EXTRA + RECON_SCHEME_THREE_EXTRA,
        "command": COMMAND_SCHEME_ONE + COMMAND_SCHEME_TWO_EXTRA + COMMAND_SCHEME_THREE_EXTRA,
        "fire": FIRE_SCHEME_ONE + FIRE_SCHEME_TWO_EXTRA + FIRE_SCHEME_THREE_EXTRA,
    },
]

AMMO_COSTS = {
    # 采用相对量级的示例成本，避免 0 值导致评估结果失真
    "火箭弹": 5000.0,
    "巡飞弹": 80000.0,
    "122榴弹炮": 1500.0,
    "坦克炮": 2000.0,
    "红箭-10": 50000.0,
    "远程火箭炮-加强型": 12000.0,
    "制导火箭弹": 15000.0,
    "远程巡飞弹": 18000.0,
    "战术导弹": 20000.0,
    "区域防空导弹": 24000.0,
    "反舰导弹": 26000.0,
    "战术巡航导弹": 30000.0,
}

AMMO_PAYLOADS: List[Dict[str, Any]] = [
    ammo_payload(
        "火箭弹",
        precision_value=30.0,
        ammo_count=8,
        max_range=18.0,
        conversion_coeff=2.5,
        flight_time=120.0,
        cost=AMMO_COSTS["火箭弹"],
    ),
    ammo_payload(
        "巡飞弹",
        precision_value=1.5,
        ammo_count=16,
        max_range=60.0,
        conversion_coeff=1.2,
        flight_time=721.0,
        cost=AMMO_COSTS["巡飞弹"],
    ),
    ammo_payload(
        "122榴弹炮",
        precision_value=10.0,
        ammo_count=40,
        max_range=15.0,
        conversion_coeff=1.0,
        flight_time=100.0,
        cost=AMMO_COSTS["122榴弹炮"],
    ),
    ammo_payload(
        "坦克炮",
        precision_value=2.0,
        ammo_count=20,
        max_range=2.5,
        conversion_coeff=0.9,
        flight_time=40.0,
        cost=AMMO_COSTS["坦克炮"],
    ),
    ammo_payload(
        "红箭-10",
        precision_value=2.0,
        ammo_count=8,
        max_range=16.0,
        conversion_coeff=1.5,
        flight_time=76.0,
        cost=AMMO_COSTS["红箭-10"],
    ),
    ammo_payload(
        "远程火箭炮-加强型",
        precision_value=8.0,
        ammo_count=12,
        max_range=20.0,
        conversion_coeff=1.0,
        flight_time=130.0,
        cost=AMMO_COSTS["远程火箭炮-加强型"],
    ),
    ammo_payload(
        "制导火箭弹",
        precision_value=5.0,
        ammo_count=12,
        max_range=25.0,
        conversion_coeff=1.0,
        flight_time=90.0,
        cost=AMMO_COSTS["制导火箭弹"],
    ),
    ammo_payload(
        "远程巡飞弹",
        precision_value=4.0,
        ammo_count=12,
        max_range=30.0,
        conversion_coeff=1.0,
        flight_time=150.0,
        cost=AMMO_COSTS["远程巡飞弹"],
    ),
    ammo_payload(
        "战术导弹",
        precision_value=6.0,
        ammo_count=12,
        max_range=35.0,
        conversion_coeff=1.0,
        flight_time=160.0,
        cost=AMMO_COSTS["战术导弹"],
    ),
    ammo_payload(
        "区域防空导弹",
        precision_value=4.5,
        ammo_count=12,
        max_range=25.0,
        conversion_coeff=1.0,
        flight_time=130.0,
        cost=AMMO_COSTS["区域防空导弹"],
    ),
    ammo_payload(
        "反舰导弹",
        precision_value=7.0,
        ammo_count=12,
        max_range=28.0,
        conversion_coeff=1.0,
        flight_time=110.0,
        cost=AMMO_COSTS["反舰导弹"],
    ),
    ammo_payload(
        "战术巡航导弹",
        precision_value=3.5,
        ammo_count=12,
        max_range=40.0,
        conversion_coeff=1.0,
        flight_time=180.0,
        cost=AMMO_COSTS["战术巡航导弹"],
    ),
]


def ensure_scheme(repo: MySQLRepository, scheme_name: str) -> str:
    """获取或创建方案 ID，便于脚本重复执行。"""
    row = repo.fetch_one(
        "SELECT scheme_id FROM scheme_master WHERE scheme_name = %s LIMIT 1",
        (scheme_name,),
    )
    if row:
        return str(row[0])
    scheme_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, scheme_name))
    try:
        repo.execute(
            "INSERT INTO scheme_master (scheme_id, scheme_name, creator) VALUES (%s, %s, %s)",
            (scheme_id, scheme_name, CREATOR),
        )
    except IntegrityError:
        # 若已有相同 scheme_id（前一次导入留下），直接读取并复用，保证脚本幂等
        existing = repo.fetch_one(
            "SELECT scheme_id FROM scheme_master WHERE scheme_id = %s LIMIT 1",
            (scheme_id,),
        )
        if existing:
            return str(existing[0])
        raise
    return scheme_id


def upsert_ammo(repo: MySQLRepository, payloads: Sequence[Dict[str, Any]]) -> None:
    """按弹药类型覆盖写入，避免重复导入时出现多条记录。"""
    if not payloads:
        return
    ammo_types = [item["ammo_type"] for item in payloads]
    placeholders = ", ".join(["%s"] * len(ammo_types))
    with repo.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM ammo_data WHERE ammo_type IN ({placeholders})", ammo_types)
            cur.executemany(
                """
                INSERT INTO ammo_data (
                    ammo_type, precision_value, ammo_count, max_range, damage_radius,
                    conversion_coeff, flight_time, cost
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        item["ammo_type"],
                        item["precision_value"],
                        item["ammo_count"],
                        item["max_range"],
                        item["damage_radius"],
                        item["conversion_coeff"],
                        item["flight_time"],
                        item["cost"],
                    )
                    for item in payloads
                ],
            )
        conn.commit()


def replace_nodes(node_service: NodeService, scheme_id: str, node_type: str, data: List[Dict[str, Any]]) -> None:
    cfg = NODE_TYPES[node_type]
    columns = ["scheme_id"] + cfg["fields"][1:]
    rows = [[scheme_id] + [item.get(field) for field in cfg["fields"][1:]] for item in data]
    node_service.replace_nodes(cfg["table_name"], columns, scheme_id, rows)


def main() -> None:
    repo = MySQLRepository(DATABASE_CONFIG)
    node_service = NodeService(repo)

    upsert_ammo(repo, AMMO_PAYLOADS)

    for scheme in SCHEMES:
        scheme_id = ensure_scheme(repo, scheme["scheme_name"])
        replace_nodes(node_service, scheme_id, "target", scheme["targets"])
        replace_nodes(node_service, scheme_id, "recon", scheme["recon"])
        replace_nodes(node_service, scheme_id, "command", scheme["command"])
        replace_nodes(node_service, scheme_id, "fire", scheme["fire"])
        print(f"已写入方案“{scheme['scheme_name']}”（{scheme['description']}），scheme_id={scheme_id}")


if __name__ == "__main__":
    main()
