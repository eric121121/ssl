"""方案元数据的业务封装。"""
from __future__ import annotations

from typing import Iterable, Tuple

from repositories.mysql_repository import MySQLRepository


class SchemeService:
    """
    封装 scheme_master 及其节点表的 CRUD 操作。

    Repository 层仅执行 SQL，Service 则提供语义化接口，UI/对话框无需感知 SQL 细节。
    """

    def __init__(self, repository: MySQLRepository):
        self._repository = repository

    def fetch_all_for_cache(self) -> Tuple[Tuple, ...]:
        """按拟制时间升序返回方案列表，供内存缓存使用。"""
        query = (
            "SELECT scheme_id, scheme_name, creator, created_time "
            "FROM scheme_master ORDER BY created_time"
        )
        return self._repository.fetch_all(query)

    def fetch_all_for_panel(self) -> Tuple[Tuple, ...]:
        """按拟制时间降序返回方案列表，供 UI 表格展示。"""
        query = (
            "SELECT scheme_id, scheme_name, created_time, creator "
            "FROM scheme_master ORDER BY created_time DESC"
        )
        return self._repository.fetch_all(query)

    def update_scheme_name(self, scheme_id: str, scheme_name: str) -> None:
        self._repository.execute(
            "UPDATE scheme_master SET scheme_name = %s WHERE scheme_id = %s",
            (scheme_name, scheme_id),
        )

    def update_scheme_creator(self, scheme_id: str, creator: str) -> None:
        self._repository.execute(
            "UPDATE scheme_master SET creator = %s WHERE scheme_id = %s",
            (creator, scheme_id),
        )

    def update_scheme(self, scheme_id: str, scheme_name: str, creator: str) -> None:
        self._repository.execute(
            "UPDATE scheme_master SET scheme_name = %s, creator = %s WHERE scheme_id = %s",
            (scheme_name, creator, scheme_id),
        )

    def create_scheme(self, scheme_id: str, scheme_name: str, creator: str) -> None:
        self._repository.execute(
            "INSERT INTO scheme_master (scheme_id, scheme_name, creator) VALUES (%s, %s, %s)",
            (scheme_id, scheme_name, creator),
        )

    def delete_scheme_and_nodes(self, scheme_id: str) -> None:
        tables: Iterable[str] = (
            "reconnaissance_nodes",
            "command_nodes",
            "firepower_nodes",
            "target_nodes",
        )
        with self._repository.connection() as conn:
            with conn.cursor() as cur:
                # 节点表依赖 scheme_id 外键，先删子表再删主表，避免约束冲突。
                for table in tables:
                    cur.execute(f"DELETE FROM {table} WHERE scheme_id = %s", (scheme_id,))
                cur.execute("DELETE FROM scheme_master WHERE scheme_id = %s", (scheme_id,))
            conn.commit()

    def count_targets(self, scheme_id: str) -> int:
        row = self._repository.fetch_one(
            "SELECT COUNT(*) FROM target_nodes WHERE scheme_id = %s", (scheme_id,)
        )
        return int(row[0]) if row else 0
