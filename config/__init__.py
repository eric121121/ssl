# -*- coding: utf-8 -*-
"""
统一配置文件，集中保存 UI 与服务层共享的静态配置。

模块分为三部分：
1. `DATABASE_CONFIG`：提供 MySQL 连接参数，方便 `MySQLRepository` 直接解包。
2. `NODE_TYPES`：描述四类节点表的字段/列标题，用于节点编辑器自动生成列。
3. `AMMO_CONFIG`：弹药表的列定义，供弹药管理面板与导入导出复用。
"""

# 数据库配置
# 与 pymysql.connect 参数一一对应，服务层只需 `connect(**DATABASE_CONFIG)`。
DATABASE_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "11161116",
    "database": "ssl_3",
    "charset": "utf8mb4",
    "autocommit": True,
}

# 节点类型配置
# 每个节点类型都包含表名、界面显示标题、字段顺序等信息。
# NodeService 根据该配置决定 INSERT/UPDATE 的列顺序，SchemeNodesEditor 用来构造表头。
NODE_TYPES = {
    'recon': {
        'table_name': 'reconnaissance_nodes',
        'headers': ['节点ID', '节点名称', '侦察类型', '并行上限', '侦察范围', '侦察精度', '处理时间', 'X坐标', 'Y坐标', '高程', '速度X', '速度Y', '速度H'],
        'fields': ['node_id', 'node_name', 'model', 'parallel_limit', 'recon_range', 'recon_precision', 'processing_time', 'x', 'y', 'h', 'vx', 'vy', 'vh'],
        'processing_time_col': 6,
        'coord_cols': (7, 8)
    },
    'command': {
        'table_name': 'command_nodes', 
        'headers': ['节点ID', '节点名称', '指挥容量', '通信距离', '处理时间', 'X坐标', 'Y坐标', '高程', '速度X', '速度Y', '速度H'],
        'fields': ['node_id', 'node_name', 'command_capacity', 'comm_distance', 'processing_time', 'x', 'y', 'h', 'vx', 'vy', 'vh'],
        'processing_time_col': 4,
        'coord_cols': (5, 6)
    },
    'fire': {
        'table_name': 'firepower_nodes',
        'headers': ['节点ID', '节点名称', '火力类型', '弹药类型', '通信距离', '处理时间', 'X坐标', 'Y坐标', '高程', '速度X', '速度Y', '速度H'],
        'fields': ['node_id', 'node_name', 'firepower_type', 'ammo_type', 'comm_distance', 'processing_time', 'x', 'y', 'h', 'vx', 'vy', 'vh'],
        'processing_time_col': 5,
        'coord_cols': (6, 7)
    },
    'target': {
        'table_name': 'target_nodes',
        'headers': ['节点ID', '节点名称', '目标类型', '威胁度', 'X坐标', 'Y坐标', '高程', '速度X', '速度Y', '速度H'],
        'fields': ['node_id', 'node_name', 'target_type', 'threat_level', 'x', 'y', 'h', 'vx', 'vy', 'vh'],
        'processing_time_col': None,
        'coord_cols': (4, 5)
    }
}

# 弹药数据表配置
# SchemeNodesEditor 在“弹药管理” Tab 中读取该结构自动构建列。
# `fields` 的顺序与数据库列完全一致，便于直接拼接 SQL。
AMMO_CONFIG = {
    'table_name': 'ammo_data',
    'headers': ['ID', '弹药类型', '精度', '弹药数量', '最大射程', '毁伤半径', '折算系数', '飞行时间(秒)', '成本'],
    'fields': ['id', 'ammo_type', 'precision_value', 'ammo_count', 'max_range', 'damage_radius', 'conversion_coeff', 'flight_time', 'cost']
}
