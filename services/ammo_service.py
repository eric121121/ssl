"""弹药数据访问服务。"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from repositories.mysql_repository import MySQLRepository


class AmmoService:
    """围绕 ammo_data 表的 CRUD 封装。"""

    def __init__(self, repository: MySQLRepository):
        self._repository = repository

    def fetch_all(self):
        """返回全部弹药条目，供 UI 表格展示。"""
        query = (
            "SELECT id, ammo_type, precision_value, ammo_count, max_range, "
            "damage_radius, conversion_coeff, flight_time, cost "
            "FROM ammo_data ORDER BY id"
        )
        return self._repository.fetch_all(query)

    def get_by_type(self, ammo_type: str) -> Optional[Dict[str, float]]:
        """按弹药名称查询详细参数，供算法或编辑对话框使用。"""
        row = self._repository.fetch_one(
            """
            SELECT id, ammo_type, precision_value, ammo_count, max_range,
                   damage_radius, conversion_coeff, flight_time, cost
            FROM ammo_data WHERE ammo_type = %s
            """,
            (ammo_type,),
        )
        if not row:
            return None
        (
            ammo_id,
            ammo_type,
            precision_value,
            ammo_count,
            max_range,
            damage_radius,
            conversion_coeff,
            flight_time,
            cost,
        ) = row
        return {
            "id": ammo_id,
            "ammo_type": ammo_type,
            "precision_value": precision_value,
            "ammo_count": ammo_count,
            "max_range": max_range,
            "damage_radius": damage_radius,
            "conversion_coeff": conversion_coeff,
            "flight_time": flight_time,
            "cost": cost,
        }

    def upsert_ammo(
        self,
        ammo_type: str,
        precision_value: float,
        ammo_count: int,
        max_range: float,
        damage_radius: float,
        conversion_coeff: float,
        flight_time: float,
        cost: float,
    ) -> None:
        with self._repository.connection() as conn:
            with conn.cursor() as cur:
                # MySQL `ON DUPLICATE KEY` 语法让我们可以复用同一套 SQL 完成插入/更新。
                cur.execute(
                    """
                    INSERT INTO ammo_data (
                        ammo_type, precision_value, ammo_count, max_range,
                        damage_radius, conversion_coeff, flight_time, cost
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        precision_value = VALUES(precision_value),
                        ammo_count = VALUES(ammo_count),
                        max_range = VALUES(max_range),
                        damage_radius = VALUES(damage_radius),
                        conversion_coeff = VALUES(conversion_coeff),
                        flight_time = VALUES(flight_time),
                        cost = VALUES(cost)
                    """,
                    (
                        ammo_type,
                        precision_value,
                        ammo_count,
                        max_range,
                        damage_radius,
                        conversion_coeff,
                        flight_time,
                        cost,
                    ),
                )
            conn.commit()

    def delete_by_types(self, ammo_types: Sequence[str]):
        """批量删除指定 ammo_type，传入空列表时直接返回。"""
        if not ammo_types:
            return
        with self._repository.connection() as conn:
            with conn.cursor() as cur:
                for ammo_type in ammo_types:
                    cur.execute("DELETE FROM ammo_data WHERE ammo_type = %s", (ammo_type,))
            conn.commit()

    def replace_all(self, rows: List[List]):
        """清空表后重新写入，为批量导入 Excel 数据提供便利。"""
        with self._repository.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM ammo_data")
                if rows:
                    for row in rows:
                        cur.execute(
                            """
                            INSERT INTO ammo_data
                            (ammo_type, precision_value, ammo_count, max_range,
                             damage_radius, conversion_coeff, flight_time, cost)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            row,
                        )
            conn.commit()
