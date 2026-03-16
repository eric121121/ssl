"""节点数据访问层，供 UI 与算法共用。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from repositories.mysql_repository import MySQLRepository
from config import NODE_TYPES


class NodeService:
    """针对指定方案返回结构化节点数据，并提供节点管理接口。"""

    def __init__(self, repository: MySQLRepository):
        self._repository = repository

    def load_scheme_nodes(self, scheme_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """一次性加载当前方案的全部节点，供画布和算法使用。"""
        return {
            'targets': self._fetch_targets(scheme_id),
            'recon': self._fetch_recon_nodes(scheme_id),
            'command': self._fetch_command_nodes(scheme_id),
            'fire': self._fetch_fire_nodes(scheme_id),
        }

    # ---- 通用节点编辑器辅助 ----
    def fetch_raw_nodes(self, table_name: str, columns: List[str], scheme_id: str):
        """节点编辑器使用的通用查询，返回原始 SQL 结果。"""
        cols_str = ', '.join(columns)
        query = f"SELECT {cols_str} FROM {table_name} WHERE scheme_id = %s ORDER BY node_id"
        return self._repository.fetch_all(query, (scheme_id,))

    def fetch_all_raw_nodes(self, table_name: str, columns: List[str]):
        """不带方案过滤的查询，用于跨方案统计。"""
        cols_str = ', '.join(columns)
        query = f"SELECT {cols_str} FROM {table_name} ORDER BY node_id"
        return self._repository.fetch_all(query)

    def delete_nodes(self, table_name: str, scheme_id: str, node_ids):
        """按 node_id 列表逐条删除。"""
        if not node_ids:
            return
        with self._repository.connection() as conn:
            with conn.cursor() as cur:
                for node_id in node_ids:
                    cur.execute(
                        f"DELETE FROM {table_name} WHERE scheme_id = %s AND node_id = %s",
                        (scheme_id, node_id),
                    )
            conn.commit()

    def insert_nodes(self, table_name: str, columns: List[str], rows: List[List[Any]]):
        """插入一组节点，`rows` 的列顺序需与 columns 对齐。"""
        if not rows:
            return
        placeholders = ', '.join(['%s'] * len(columns))
        cols_str = ', '.join(columns)
        with self._repository.connection() as conn:
            with conn.cursor() as cur:
                for row in rows:
                    cur.execute(
                        f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})",
                        row,
                    )
            conn.commit()

    def replace_nodes(self, table_name: str, columns: List[str], scheme_id: str, rows: List[List[Any]]):
        """
        删除方案已有节点后再插入新数据，用于“覆盖式”导入。

        采用“全量删除 + 重新插入”而不是逐条 UPDATE，可以保证用户在节点编辑器中编辑时不会
        遗漏任何列，同时也避免了复杂的差异同步逻辑。
        """
        with self._repository.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {table_name} WHERE scheme_id = %s", (scheme_id,))
                if rows:
                    placeholders = ', '.join(['%s'] * len(columns))
                    cols_str = ', '.join(columns)
                    for row in rows:
                        cur.execute(
                            f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})",
                            row,
                        )
            conn.commit()

    def upsert_node(self, node_type: str, scheme_id: str, data: Dict[str, Any], node_id: Optional[int] = None) -> int:
        """
        插入或更新单个节点。

        node_editor 会传递 node_type（在 NODE_TYPES 中定义字段顺序），这里根据
        是否有 node_id 决定先删后插还是直接插入新记录。
        """
        cfg = NODE_TYPES[node_type]
        table = cfg['table_name']
        with self._repository.connection() as conn:
            with conn.cursor() as cur:
                if node_id is not None:
                    # 有 node_id 时先移除原记录，再用固定 ID 重建，保证自增列保持原值。
                    cur.execute(f"DELETE FROM {table} WHERE node_id = %s", (node_id,))
                    columns = ['scheme_id'] + cfg['fields']
                    values = [scheme_id, node_id]
                else:
                    # 新节点无需传 node_id，由数据库自增生成；字段从第二个元素开始取。
                    columns = ['scheme_id'] + cfg['fields'][1:]
                    values = [scheme_id]
                for field in cfg['fields'][1:]:
                    values.append(data.get(field))
                placeholders = ', '.join(['%s'] * len(columns))
                cols_str = ', '.join(columns)
                cur.execute(
                    f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders})",
                    values,
                )
                if node_id is None:
                    node_id = cur.lastrowid
            conn.commit()
        return int(node_id)

    def fetch_fire_target_preferences(self):
        """获取弹目偏好矩阵，结果列表供多目标算法转换为 dict。"""
        return self._repository.fetch_all(
            "SELECT fire_type, target_type, preference_rank FROM fire_target_preference"
        )

    def _fetch_targets(self, scheme_id: str) -> List[Dict[str, Any]]:
        """把目标节点转换成算法友好格式。"""
        rows = self._repository.fetch_all(
            """
            SELECT node_id, node_name, target_type, threat_level, x, y, h, vx, vy, vh
            FROM target_nodes
            WHERE scheme_id = %s
            ORDER BY node_id
            """,
            (scheme_id,),
        )
        targets: List[Dict[str, Any]] = []
        for idx, (_, node_name, target_type, threat_level, x, y, h, vx, vy, vh) in enumerate(rows, start=1):
            targets.append(
                {
                    'id': f't{idx}',
                    'name': node_name,
                    'type': target_type,
                    'threat_level': threat_level,
                    'coord': (x, y),
                    'h': h,
                    'vx': vx,
                    'vy': vy,
                    'vh': vh,
                }
            )
        return targets

    def _fetch_recon_nodes(self, scheme_id: str) -> List[Dict[str, Any]]:
        """解析侦察节点字段，补齐算法期望的键名。"""
        rows = self._repository.fetch_all(
            """
            SELECT node_id, node_name, model, parallel_limit, recon_range, recon_precision,
                   processing_time, x, y, h, vx, vy, vh
            FROM reconnaissance_nodes
            WHERE scheme_id = %s
            ORDER BY node_id
            """,
            (scheme_id,),
        )
        recon_nodes: List[Dict[str, Any]] = []
        for idx, row in enumerate(rows, start=1):
            (
                _db_id,
                node_name,
                model,
                parallel_limit,
                recon_range,
                recon_precision,
                processing_time,
                x,
                y,
                h,
                vx,
                vy,
                vh,
            ) = row
            recon_nodes.append(
                {
                    'id': f'o{idx}',
                    'name': node_name,
                    'model': model,
                    'coord': (x, y),
                    'range': recon_range,
                    't_deal': processing_time,
                    'sigma2': recon_precision,
                    'parallel_limit': parallel_limit,
                    'velocity': (vx, vy, vh),
                    'h': h,
                }
            )
        return recon_nodes

    def _fetch_command_nodes(self, scheme_id: str) -> List[Dict[str, Any]]:
        """
        加载指挥节点并填充双份的 range/process 字段，兼容旧算法结构。

        历史算法中既使用 `range` 也使用 `comm_range`/`process_time`/`t_deal`，因此这里把
        同一个值写入多个键，避免前端或算法访问缺失字段。
        """
        rows = self._repository.fetch_all(
            """
            SELECT node_id, node_name, command_capacity, comm_distance, processing_time,
                   x, y, h, vx, vy, vh
            FROM command_nodes
            WHERE scheme_id = %s
            ORDER BY node_id
            """,
            (scheme_id,),
        )
        command_nodes: List[Dict[str, Any]] = []
        for idx, row in enumerate(rows, start=1):
            (
                _db_id,
                node_name,
                command_capacity,
                comm_distance,
                processing_time,
                x,
                y,
                h,
                vx,
                vy,
                vh,
            ) = row
            command_nodes.append(
                {
                    'id': f'c{idx}',
                    'name': node_name,
                    'model': 'command',
                    'command_capacity': command_capacity,
                    'range': comm_distance,
                    'comm_range': comm_distance,
                    'process_time': processing_time,
                    't_deal': processing_time,
                    'coord': (x, y),
                    'h': h,
                    'vx': vx,
                    'vy': vy,
                    'vh': vh,
                }
            )
        return command_nodes

    def _fetch_fire_nodes(self, scheme_id: str) -> List[Dict[str, Any]]:
        """
        加载火力节点，并联表获取弹药参数。

        若某个弹药类型不存在于 ammo_data，则使用安全默认值，保证算法仍能运行。
        """
        rows = self._repository.fetch_all(
            """
            SELECT f.node_id,
                   f.node_name,
                   f.firepower_type,
                   f.ammo_type,
                   f.comm_distance,
                   f.processing_time,
                   f.x,
                   f.y,
                   f.h,
                   f.vx,
                   f.vy,
                   f.vh,
                   a.ammo_count,
                   a.conversion_coeff,
                   a.flight_time,
                   a.cost,
                   a.precision_value
            FROM firepower_nodes f
            LEFT JOIN ammo_data a ON f.ammo_type = a.ammo_type
            WHERE f.scheme_id = %s
            ORDER BY f.node_id
            """,
            (scheme_id,),
        )
        fire_nodes: List[Dict[str, Any]] = []
        for idx, row in enumerate(rows, start=1):
            (
                _db_id,
                node_name,
                firepower_type,
                ammo_type,
                comm_distance,
                processing_time,
                x,
                y,
                h,
                vx,
                vy,
                vh,
                ammo_count,
                conversion_coeff,
                flight_time,
                cost,
                precision_value,
            ) = row
            # ammo_data 可能为空，此处提供默认值，避免算法访问 None。
            ammo_dict = {
                'count': ammo_count if ammo_count is not None else 1,
                'omega': conversion_coeff if conversion_coeff is not None else 1.0,
                'flight_time': flight_time if flight_time is not None else 0.0,
                'cost': cost if cost is not None else 0.0,
                'precision': precision_value if precision_value is not None else 0.0,
            }
            fire_nodes.append(
                {
                    'id': f'w{idx}',
                    'name': node_name,
                    'model': firepower_type,
                    'firepower_type': firepower_type,
                    'ammo_type': ammo_type,
                    'ammo': ammo_dict,
                    'range': comm_distance,
                    'comm_range': comm_distance,
                    'process_time': processing_time,
                    't_deal': processing_time,
                    't_flight': ammo_dict['flight_time'],
                    'sigma2': ammo_dict['precision'],
                    'coord': (x, y),
                    'h': h,
                    'vx': vx,
                    'vy': vy,
                    'vh': vh,
                }
            )
        return fire_nodes
