"""提供 MySQL 连接/查询的轻量封装。"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable, Optional, Sequence, Tuple

import pymysql


Params = Optional[Sequence[Any]]


class MySQLRepository:
    """封装常用的查询/写入模式，确保连接统一由 context manager 管理。"""

    def __init__(self, config: dict[str, Any]):
        # 保存数据库配置，供每次连接时使用；不在构造函数里创建连接，避免线程间共享。
        self._config = config

    def create_connection(self) -> pymysql.connections.Connection:
        """创建裸连接；调用方需自行关闭（除非配合 `connection()` 使用）。"""
        return pymysql.connect(**self._config)

    @contextmanager
    def connection(self) -> Iterable[pymysql.connections.Connection]:
        """上下文管理器，结束时自动关闭连接。"""
        conn = self.create_connection()
        try:
            yield conn
        finally:
            conn.close()

    def fetch_all(self, query: str, params: Params = None) -> Tuple[Tuple[Any, ...], ...]:
        """执行查询并返回所有行，常用于列表页或缓存刷新。"""
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()

    def fetch_one(self, query: str, params: Params = None) -> Optional[Tuple[Any, ...]]:
        """返回首行数据，用于统计或单条查询。"""
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone()

    def execute(self, query: str, params: Params = None) -> None:
        """执行写操作，并在内部提交事务。"""
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
