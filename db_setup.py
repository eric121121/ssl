import pymysql
import random
import uuid
import math
from datetime import datetime, timedelta
from typing import Dict, Any
from config import DATABASE_CONFIG


def create_database_and_tables(db_config: Dict[str, Any], test_mode: bool = True) -> None:
	"""
	创建 MySQL 数据库 `ssl_3` 及其全部表结构。
	
	内容包括 7 张业务表，并在节点表中加入 scheme_id 字段。
	若 test_mode=True，则会自动写入多套测试方案数据（包含动目标方案）。
	
	参数：
		db_config: 数据库配置字典
		test_mode: 是否启用测试模式（默认 True）
	"""

	# 单次连接：先创建数据库，再切换到该库执行后续操作
	db_name = db_config.get("database", "ssl_3")
	conn = pymysql.connect(
		host=db_config.get("host", "127.0.0.1"),
		port=int(db_config.get("port", 3306)),
		user=db_config.get("user", "root"),
		password=db_config.get("password", "11161116"),
		charset="utf8mb4",
		autocommit=True,
	)
	with conn.cursor() as cur:
		cur.execute(
			f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
			"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
		)
	conn.select_db(db_name)
	try:
		with conn.cursor() as cur:
			# 先删除所有表以避免结构冲突
			if test_mode:
				cur.execute("DROP TABLE IF EXISTS `scheme_master`")
			cur.execute("DROP TABLE IF EXISTS `fire_target_preference`")
			cur.execute("DROP TABLE IF EXISTS `firepower_nodes`")
			cur.execute("DROP TABLE IF EXISTS `target_nodes`")
			cur.execute("DROP TABLE IF EXISTS `command_nodes`")
			cur.execute("DROP TABLE IF EXISTS `reconnaissance_nodes`")
			cur.execute("DROP TABLE IF EXISTS `ammo_data`")
			
			# 测试模式：创建方案主表
			if test_mode:
				cur.execute("""
					CREATE TABLE `scheme_master` (
						`scheme_id`        CHAR(36)     NOT NULL COMMENT '方案内码（GUID主键）',
						`scheme_name`      VARCHAR(128) NOT NULL COMMENT '方案名称',
						`created_time`     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '拟制时间',
						`creator`          VARCHAR(64)  NOT NULL COMMENT '拟制人',
						PRIMARY KEY (`scheme_id`)
					) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='SSL构建方案表';
				""")

			# 1、弹药数据表
			cur.execute(
				"""
				CREATE TABLE `ammo_data` (
					`id`               INT          NOT NULL AUTO_INCREMENT COMMENT 'ID（主键）',
					`ammo_type`        VARCHAR(64)  NOT NULL COMMENT '弹药类型',
					`precision_value`  DOUBLE       NOT NULL COMMENT '精度',
					`ammo_count`       INT          NOT NULL COMMENT '弹药数量',
					`max_range`        DOUBLE       NOT NULL COMMENT '最大射程',
					`damage_radius`    DOUBLE       NOT NULL COMMENT '毁伤半径',
					`conversion_coeff` DOUBLE       NOT NULL COMMENT '折算系数',
					`flight_time`      DOUBLE       NOT NULL COMMENT '飞行时间(秒)',
					`cost`             DECIMAL(10,2) NOT NULL COMMENT '成本',
					PRIMARY KEY (`id`)
				) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='弹药数据表';
				"""
			)

			# 2、侦察节点表
			scheme_id_field = "`scheme_id`        CHAR(36)     NOT NULL COMMENT '方案内码（GUID）',\n\t\t\t\t" if test_mode else ""
			scheme_id_index = ", INDEX `idx_scheme_id` (`scheme_id`)" if test_mode else ""
			cur.execute(f"""
				CREATE TABLE `reconnaissance_nodes` (
					{scheme_id_field}`node_id`          BIGINT      NOT NULL AUTO_INCREMENT COMMENT '节点编号（主键）',
					`node_name`        VARCHAR(128) NOT NULL COMMENT '节点名称',
					`model`            VARCHAR(64)  NOT NULL COMMENT '侦察类型',
					`parallel_limit`   INT          NOT NULL COMMENT '并行上限',
					`recon_range`      DOUBLE       NOT NULL COMMENT '侦察距离(千米)',
					`recon_precision`  DOUBLE       NOT NULL COMMENT '侦察精度',
					`processing_time`  DOUBLE       NOT NULL COMMENT '处理时间',
					`x`                DOUBLE       NOT NULL COMMENT '经度 x',
					`y`                DOUBLE       NOT NULL COMMENT '纬度 y',
					`h`                DOUBLE       NOT NULL COMMENT '高程 h',
					`vx`               DOUBLE       NOT NULL COMMENT '速度 x',
					`vy`               DOUBLE       NOT NULL COMMENT '速度 y',
					`vh`               DOUBLE       NOT NULL COMMENT '速度 h'
					{scheme_id_index},
					PRIMARY KEY (`node_id`)
				) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='侦察节点表';
			""")

			# 3、指挥节点表
			scheme_id_field = "`scheme_id`        CHAR(36)     NOT NULL COMMENT '方案内码（GUID）',\n\t\t\t\t" if test_mode else ""
			scheme_id_index = ", INDEX `idx_scheme_id` (`scheme_id`)" if test_mode else ""
			command_capacity_field = ", `command_capacity` INT NOT NULL COMMENT '指挥容量（最大同时指挥目标数）'" if test_mode else ""
			cur.execute(f"""
				CREATE TABLE `command_nodes` (
					{scheme_id_field}`node_id`          BIGINT      NOT NULL AUTO_INCREMENT COMMENT '节点编号（主键）',
					`node_name`        VARCHAR(128) NOT NULL COMMENT '节点名称'
					{command_capacity_field},
					`comm_distance`    DOUBLE       NOT NULL COMMENT '通信距离(千米)',
					`processing_time`  DOUBLE       NOT NULL COMMENT '处理时间',
					`x`                DOUBLE       NOT NULL COMMENT '经度 x',
					`y`                DOUBLE       NOT NULL COMMENT '纬度 y',
					`h`                DOUBLE       NOT NULL COMMENT '高程 h',
					`vx`               DOUBLE       NOT NULL COMMENT '速度 x',
					`vy`               DOUBLE       NOT NULL COMMENT '速度 y',
					`vh`               DOUBLE       NOT NULL COMMENT '速度 h'
					{scheme_id_index},
					PRIMARY KEY (`node_id`)
				) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='指挥节点表';
			""")

			# 4、火力节点表
			scheme_id_field = "`scheme_id`        CHAR(36)     NOT NULL COMMENT '方案内码（GUID）',\n\t\t\t\t" if test_mode else ""
			scheme_id_index = ", INDEX `idx_scheme_id` (`scheme_id`)" if test_mode else ""
			cur.execute(f"""
				CREATE TABLE `firepower_nodes` (
					{scheme_id_field}`node_id`          BIGINT      NOT NULL AUTO_INCREMENT COMMENT '节点编号（主键）',
					`node_name`        VARCHAR(128) NOT NULL COMMENT '节点名称',
					`firepower_type`   VARCHAR(64)  NOT NULL COMMENT '火力类型',
					`ammo_type`        VARCHAR(64)  NOT NULL COMMENT '弹药类型',
					`comm_distance`    DOUBLE       NOT NULL COMMENT '通信距离(千米)',
					`processing_time`  DOUBLE       NOT NULL COMMENT '处理时间',
					`x`                DOUBLE       NOT NULL COMMENT '经度 x',
					`y`                DOUBLE       NOT NULL COMMENT '纬度 y',
					`h`                DOUBLE       NOT NULL COMMENT '高程 h',
					`vx`               DOUBLE       NOT NULL COMMENT '速度 x',
					`vy`               DOUBLE       NOT NULL COMMENT '速度 y',
					`vh`               DOUBLE       NOT NULL COMMENT '速度 h'
					{scheme_id_index},
					PRIMARY KEY (`node_id`)
				) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='火力节点表';
			""")

			# 5、目标节点表
			scheme_id_field = "`scheme_id`        CHAR(36)     NOT NULL COMMENT '方案内码（GUID）',\n\t\t\t\t" if test_mode else ""
			scheme_id_index = ", INDEX `idx_scheme_id` (`scheme_id`)" if test_mode else ""
			cur.execute(f"""
				CREATE TABLE `target_nodes` (
					{scheme_id_field}`node_id`         BIGINT      NOT NULL AUTO_INCREMENT COMMENT '节点编号（主键）',
					`node_name`       VARCHAR(128) NOT NULL COMMENT '节点名称',
					`target_type`     VARCHAR(64)  NOT NULL COMMENT '目标类型',
					`threat_level`    INT          NOT NULL COMMENT '威胁度',
					`x`               DOUBLE       NOT NULL COMMENT '经度 x',
					`y`               DOUBLE       NOT NULL COMMENT '纬度 y',
					`h`               DOUBLE       NOT NULL COMMENT '高程 h',
					`vx`              DOUBLE       NOT NULL COMMENT '速度 x',
					`vy`              DOUBLE       NOT NULL COMMENT '速度 y',
					`vh`              DOUBLE       NOT NULL COMMENT '速度 h'
					{scheme_id_index},
					PRIMARY KEY (`node_id`)
				) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='目标节点表';
			""")

			# 6、弹目偏好表
			cur.execute(
				"""
				CREATE TABLE `fire_target_preference` (
					`fire_type`        VARCHAR(64)  NOT NULL COMMENT '火力类型',
					`target_type`      VARCHAR(64)  NOT NULL COMMENT '目标类型',
					`preference_rank`  INT          NOT NULL COMMENT '偏好排序(1-4,数值越小优先级越高)',
					PRIMARY KEY (`fire_type`, `target_type`)
				) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='弹目排序表';
				"""
			)

			# 插入弹药数据表初始数据
			ammo_data = [
				('迫击炮', 30, 8, 18, 0, 2.5, 120, 200.00),
				('子弹', 1.5, 8, 16, 0, 1.5, 76, 1.00),
				('导弹', 10, 16, 60, 0, 1.2, 721, 150000.00),
				('核弹', 2, 20, 2.5, 0, 0.9, 40, 10000000.00),
				('榴弹炮', 2, 40, 15, 0, 1, 100, 1500.00),
				('反坦克导弹', 5, 12, 25, 0, 1.1, 300, 50000.00),
				('防空导弹', 8, 8, 35, 0, 1.3, 180, 80000.00),
				('精确制导炸弹', 3, 6, 20, 0, 0.8, 45, 25000.00),
				('火箭弹', 15, 20, 12, 0, 1.4, 60, 5000.00),
				('激光制导炸弹', 2, 4, 18, 0, 0.7, 35, 30000.00),
			]
			
			cur.executemany(
				"""
				INSERT INTO ammo_data (ammo_type, precision_value, ammo_count, max_range, damage_radius, conversion_coeff, flight_time, cost)
				VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
				""",
				ammo_data
			)

			# 插入弹目偏好表初始数据
			preference_data = [
				('导弹发射车', '主战坦克', 1),
				('导弹发射车', '指挥所/坚固点', 2),
				('导弹发射车', '车队/纵列', 2),
				('导弹发射车', '轻步兵/散兵', 3),
				('导弹发射车', '装甲运兵车', 2),
				('导弹发射车', '炮兵阵地', 2),
				('导弹发射车', '雷达站', 1),
				('导弹发射车', '机场设施', 1),
				('导弹发射车', '通信中心', 1),
				('火炮', '主战坦克', 3),
				('火炮', '指挥所/坚固点', 2),
				('火炮', '车队/纵列', 1),
				('火炮', '轻步兵/散兵', 2),
				('火炮', '装甲运兵车', 2),
				('火炮', '炮兵阵地', 1),
				('火炮', '雷达站', 3),
				('火炮', '机场设施', 2),
				('火炮', '通信中心', 2),
				('反坦克导弹车', '主战坦克', 1),
				('反坦克导弹车', '指挥所/坚固点', 3),
				('反坦克导弹车', '车队/纵列', 2),
				('反坦克导弹车', '轻步兵/散兵', 4),
				('反坦克导弹车', '装甲运兵车', 1),
				('反坦克导弹车', '炮兵阵地', 3),
				('反坦克导弹车', '雷达站', 4),
				('反坦克导弹车', '机场设施', 3),
				('反坦克导弹车', '通信中心', 3),
				('防空导弹车', '主战坦克', 4),
				('防空导弹车', '指挥所/坚固点', 3),
				('防空导弹车', '车队/纵列', 3),
				('防空导弹车', '轻步兵/散兵', 2),
				('防空导弹车', '装甲运兵车', 4),
				('防空导弹车', '炮兵阵地', 3),
				('防空导弹车', '雷达站', 2),
				('防空导弹车', '机场设施', 1),
				('防空导弹车', '通信中心', 2),
				('火箭炮', '主战坦克', 3),
				('火箭炮', '指挥所/坚固点', 2),
				('火箭炮', '车队/纵列', 1),
				('火箭炮', '轻步兵/散兵', 1),
				('火箭炮', '装甲运兵车', 2),
				('火箭炮', '炮兵阵地', 1),
				('火箭炮', '雷达站', 3),
				('火箭炮', '机场设施', 2),
				('火箭炮', '通信中心', 2),
				('迫击炮', '主战坦克', 4),
				('迫击炮', '指挥所/坚固点', 3),
				('迫击炮', '车队/纵列', 2),
				('迫击炮', '轻步兵/散兵', 1),
				('迫击炮', '装甲运兵车', 3),
				('迫击炮', '炮兵阵地', 2),
				('迫击炮', '雷达站', 4),
				('迫击炮', '机场设施', 3),
				('迫击炮', '通信中心', 3),
				('狙击手', '主战坦克', 4),
				('狙击手', '指挥所/坚固点', 2),
				('狙击手', '车队/纵列', 3),
				('狙击手', '轻步兵/散兵', 1),
				('狙击手', '装甲运兵车', 4),
				('狙击手', '炮兵阵地', 3),
				('狙击手', '雷达站', 2),
				('狙击手', '机场设施', 4),
				('狙击手', '通信中心', 2),
				('攻击无人机', '主战坦克', 2),
				('攻击无人机', '指挥所/坚固点', 1),
				('攻击无人机', '车队/纵列', 2),
				('攻击无人机', '轻步兵/散兵', 3),
				('攻击无人机', '装甲运兵车', 2),
				('攻击无人机', '炮兵阵地', 2),
				('攻击无人机', '雷达站', 1),
				('攻击无人机', '机场设施', 1),
				('攻击无人机', '通信中心', 1),
			]
			
			cur.executemany(
				"""
				INSERT INTO `fire_target_preference` (fire_type, target_type, preference_rank)
				VALUES (%s, %s, %s)
				""",
				preference_data
			)

			# 插入测试数据（包含动目标方案）
			if test_mode:
				_insert_test_data(cur)

	finally:
		conn.close()


def _insert_test_data(cursor):
	"""插入测试数据：5个动目标多目标方案和5个动目标单目标方案"""
	base_time = datetime.now()
	
	# 插入5个动目标多目标方案
	_insert_moving_target_multi_schemes(cursor, base_time)
	
	# 插入5个动目标单目标方案
	_insert_moving_target_single_schemes(cursor, base_time + timedelta(minutes=5))


def _insert_moving_target_multi_schemes(cursor, base_time: datetime):
	"""插入5个动目标多目标方案"""
	schemes = _get_moving_target_multi_scenarios()
	
	for idx, scheme in enumerate(schemes):
		scheme_id = str(uuid.uuid4())
		created_time = base_time + timedelta(seconds=idx)
		
		cursor.execute("""
			INSERT INTO scheme_master (scheme_id, scheme_name, creator, created_time)
			VALUES (%s, %s, %s, %s)
		""", (scheme_id, scheme['name'], scheme['creator'], created_time))
		
		# 插入各类节点
		_insert_scheme_nodes(cursor, scheme_id, scheme)


def _insert_moving_target_single_schemes(cursor, base_time: datetime):
	"""插入5个动目标单目标方案"""
	schemes = _get_moving_target_single_scenarios()
	
	for idx, scheme in enumerate(schemes):
		scheme_id = str(uuid.uuid4())
		created_time = base_time + timedelta(seconds=idx)
		
		cursor.execute("""
			INSERT INTO scheme_master (scheme_id, scheme_name, creator, created_time)
			VALUES (%s, %s, %s, %s)
		""", (scheme_id, scheme['name'], scheme['creator'], created_time))
		
		# 插入各类节点
		_insert_scheme_nodes(cursor, scheme_id, scheme)


def _get_moving_target_multi_scenarios():
	"""获取5个动目标多目标方案配置 - 坐标范围：X: -40~40, Y: 5~45"""
	return [
		{
			'name': '动目标方案一-沿海机动防御',
			'creator': '张三',
			'recon': [
				# 侦察节点：X: -20~0, Y: 20~35
				('沿岸雷达A', '地面雷达', 20, 12.0, 2.4, 1.0, -15.0, 30.0, 1.2, 0, 0, 0),
				('沿岸光电A', '光电无人机', 6, 10.5, 1.2, 4.8, -10.0, 28.0, 0.5, 0, 0, 0),
				('高空雷达A', '雷达无人机', 12, 14.0, 1.6, 4.0, -5.0, 32.0, 3.0, 0, 0, 0),
			],
			'command': [
				# 指挥节点：X: -25~-10, Y: 15~25
				('沿岸联指A', 8, 18.0, 3.2, -20.0, 22.0, 1.0, 0, 0, 0),
				('机动指挥A', 6, 15.5, 3.8, -15.0, 20.0, 0.6, 0, 0, 0),
			],
			'fire': [
				# 火力节点：X: -35~-20, Y: 10~20
				('岸防导弹A', '导弹发射车', '导弹', 24.0, 7.5, -30.0, 18.0, 0.5, 0, 0, 0),
				('野战火炮A', '火炮', '榴弹炮', 20.0, 6.8, -25.0, 15.0, 0.4, 0, 0, 0),
				('火箭炮旅A', '火箭炮', '火箭弹', 22.0, 9.0, -22.0, 12.0, 0.5, 0, 0, 0),
			],
			'targets': [
				# 目标节点：X: 10~35, Y: 25~40（在显示范围内移动）
				# 动目标：vx=2, vy=1.5 (向右上方移动)
				('敌海岸炮位A', '炮兵阵地', 3, 15.0, 30.0, 0.5, 2.0, 1.5, 0),
				('敌指控节点A', '通信中心', 4, 20.0, 28.0, 1.0, 1.5, 2.0, 0),
				('敌机场A', '机场设施', 5, 25.0, 35.0, 0.0, 0, 0, 0),  # 静止目标
				('敌装甲纵队A', '主战坦克', 3, 18.0, 32.0, 0.0, 2.5, 1.0, 0),
				('敌补给点A', '车队/纵列', 2, 22.0, 26.0, 0.0, 1.0, 2.5, 0),
			]
		},
		{
			'name': '动目标方案二-城市追击',
			'creator': '李四',
			'recon': [
				('城区雷达U', '地面雷达', 18, 11.5, 2.2, 1.1, -18.0, 25.0, 1.1, 0, 0, 0),
				('城区光电U', '光电无人机', 6, 9.0, 1.0, 4.2, -12.0, 22.0, 0.6, 0, 0, 0),
				('高空雷达U', '雷达无人机', 12, 14.0, 1.6, 3.4, -8.0, 28.0, 4.0, 0, 0, 0),
			],
			'command': [
				('都市联指U', 8, 17.0, 3.3, -22.0, 20.0, 1.0, 0, 0, 0),
				('机动指挥U', 6, 14.5, 3.6, -16.0, 18.0, 0.6, 0, 0, 0),
			],
			'fire': [
				('城市防空U', '防空导弹车', '防空导弹', 19.0, 4.8, -28.0, 16.0, 0.8, 0, 0, 0),
				('重炮阵地U', '火炮', '榴弹炮', 18.5, 6.5, -24.0, 14.0, 0.5, 0, 0, 0),
				('火箭支援U', '火箭炮', '火箭弹', 20.0, 8.0, -20.0, 12.0, 0.7, 0, 0, 0),
			],
			'targets': [
				# 动目标：vx=-1.5, vy=2 (向左上方移动)
				('敌通信塔U', '通信中心', 3, 30.0, 25.0, 0.0, -1.5, 2.0, 0),
				('敌指挥楼U', '指挥所/坚固点', 4, 35.0, 22.0, 0.0, -2.0, 1.5, 0),
				('敌机场跑道U', '机场设施', 5, 32.0, 30.0, 0.0, 0, 0, 0),  # 静止
				('敌装甲突击U', '主战坦克', 3, 28.0, 20.0, 0.0, -2.5, 1.0, 0),
				('敌防空阵地U', '防空阵地', 4, 25.0, 28.0, 0.0, -1.0, 2.5, 0),
			]
		},
		{
			'name': '动目标方案三-山谷拦截',
			'creator': '王五',
			'recon': [
				('山谷雷达M', '地面雷达', 22, 11.5, 2.2, 1.1, -12.0, 32.0, 1.5, 0, 0, 0),
				('峡谷雷达M', '地面雷达', 20, 10.8, 2.0, 1.0, -8.0, 30.0, 1.2, 0, 0, 0),
				('高空无人M', '雷达无人机', 12, 14.0, 1.6, 4.0, -5.0, 35.0, 3.5, 0, 0, 0),
			],
			'command': [
				('山前联指M', 7, 17.0, 3.2, -18.0, 28.0, 1.0, 0, 0, 0),
				('高机动指挥M', 6, 15.0, 3.5, -14.0, 25.0, 0.8, 0, 0, 0),
			],
			'fire': [
				('高原导弹M', '导弹发射车', '导弹', 24.0, 7.8, -32.0, 22.0, 0.6, 0, 0, 0),
				('山地火炮M', '火炮', '榴弹炮', 19.0, 6.4, -26.0, 18.0, 0.5, 0, 0, 0),
				('火箭炮M', '火箭炮', '火箭弹', 21.0, 8.5, -22.0, 15.0, 0.7, 0, 0, 0),
			],
			'targets': [
				# 动目标：vx=2, vy=-1 (向右下方移动)
				('敌山口防空M', '防空阵地', 4, 12.0, 38.0, 0.0, 2.0, -1.0, 0),
				('敌山谷指挥M', '指挥所/坚固点', 4, 18.0, 35.0, 0.0, 1.5, -1.5, 0),
				('敌补给洞库M', '通信中心', 3, 15.0, 32.0, 0.0, 0, 0, 0),  # 静止
				('敌装甲穿插M', '装甲运兵车', 3, 20.0, 30.0, 0.0, 2.5, -0.5, 0),
				('敌远程火力M', '炮兵阵地', 4, 25.0, 40.0, 0.0, 1.0, -2.0, 0),
			]
		},
		{
			'name': '动目标方案四-沙漠追击',
			'creator': '赵六',
			'recon': [
				('沙漠雷达D', '地面雷达', 20, 11.0, 2.0, 1.2, -20.0, 20.0, 1.0, 0, 0, 0),
				('长航无人D', '雷达无人机', 12, 15.0, 1.5, 3.5, -10.0, 25.0, 3.0, 0, 0, 0),
				('低空光电D', '光电无人机', 6, 9.5, 1.1, 4.3, -15.0, 22.0, 0.6, 0, 0, 0),
			],
			'command': [
				('沙漠联指D', 8, 18.0, 3.0, -25.0, 18.0, 0.8, 0, 0, 0),
				('机动指挥D', 6, 15.0, 3.4, -18.0, 15.0, 0.6, 0, 0, 0),
			],
			'fire': [
				('远程导弹D', '导弹发射车', '导弹', 25.0, 8.0, -35.0, 12.0, 0.5, 0, 0, 0),
				('重炮营D', '火炮', '榴弹炮', 20.0, 6.2, -28.0, 10.0, 0.4, 0, 0, 0),
				('火箭营D', '火箭炮', '火箭弹', 22.0, 8.7, -22.0, 8.0, 0.6, 0, 0, 0),
			],
			'targets': [
				# 动目标：vx=-2, vy=-1.5 (向左下方移动)
				('敌补给枢纽D', '车队/纵列', 3, 30.0, 20.0, 0.0, -2.0, -1.5, 0),
				('敌油料库D', '通信中心', 3, 35.0, 18.0, 0.0, -1.5, -2.0, 0),
				('敌沙漠机场D', '机场设施', 5, 32.0, 25.0, 0.0, 0, 0, 0),  # 静止
				('敌装甲掩体D', '主战坦克', 3, 28.0, 15.0, 0.0, -2.5, -1.0, 0),
				('敌远程火力D', '炮兵阵地', 4, 25.0, 22.0, 0.0, -1.0, -2.5, 0),
			]
		},
		{
			'name': '动目标方案五-岛链机动',
			'creator': '钱七',
			'recon': [
				('岛链雷达I', '地面雷达', 22, 12.0, 2.2, 1.1, -8.0, 28.0, 1.3, 0, 0, 0),
				('岛屿光电I', '光电无人机', 6, 10.0, 1.1, 4.8, -5.0, 25.0, 0.6, 0, 0, 0),
				('舰载无人I', '雷达无人机', 12, 14.5, 1.5, 3.8, -2.0, 30.0, 3.0, 0, 0, 0),
			],
			'command': [
				('沿海联指I', 8, 18.5, 3.1, -12.0, 24.0, 1.0, 0, 0, 0),
				('两栖指挥I', 6, 16.0, 3.6, -8.0, 22.0, 0.8, 0, 0, 0),
			],
			'fire': [
				('岸防导弹I', '导弹发射车', '导弹', 24.5, 7.6, -18.0, 20.0, 0.5, 0, 0, 0),
				('舰炮支援I', '火炮', '榴弹炮', 19.5, 6.5, -15.0, 16.0, 0.4, 0, 0, 0),
				('远程火箭I', '火箭炮', '火箭弹', 22.0, 8.5, -10.0, 12.0, 0.6, 0, 0, 0),
			],
			'targets': [
				# 动目标：vx=1, vy=1.5 (向右上方缓慢移动)
				('敌登陆舰队I', '车队/纵列', 3, 8.0, 32.0, 0.0, 1.0, 1.5, 0),
				('敌临时指挥I', '指挥所/坚固点', 4, 15.0, 30.0, 0.0, 1.5, 1.0, 0),
				('敌海岸炮I', '炮兵阵地', 4, 20.0, 35.0, 0.0, 0, 0, 0),  # 静止
				('敌机场跑道I', '机场设施', 5, 25.0, 38.0, 0.0, 0.5, 1.0, 0),
				('敌防空节点I', '防空阵地', 4, 12.0, 28.0, 0.0, 2.0, 0.5, 0),
			]
		},
	]


def _get_moving_target_single_scenarios():
	"""获取5个动目标单目标方案配置 - 坐标范围：X: -40~40, Y: 5~45"""
	return [
		{
			'name': '动目标单方案一-追击坦克',
			'creator': '演示员A',
			'recon': [
				('侦察无人机1', '光电无人机', 8, 35.0, 1.2, 3.5, -15.0, 25.0, 0.5, 0, 0, 0),
				('地面雷达1', '地面雷达', 20, 30.0, 2.0, 1.5, -10.0, 28.0, 1.0, 0, 0, 0),
			],
			'command': [
				('前线指挥所', 6, 35.0, 2.5, -20.0, 22.0, 0.8, 0, 0, 0),
			],
			'fire': [
				('反坦克导弹车1', '反坦克导弹车', '反坦克导弹', 30.0, 5.0, -30.0, 15.0, 0.5, 0, 0, 0),
				('火炮阵地1', '火炮', '榴弹炮', 28.0, 6.0, -25.0, 12.0, 0.4, 0, 0, 0),
			],
			'targets': [
				# 单动目标：vx=3, vy=1.5 (快速向右上方移动)
				('敌方坦克', '主战坦克', 3, 5.0, 30.0, 0.0, 3.0, 1.5, 0),
			]
		},
		{
			'name': '动目标单方案二-拦截车队',
			'creator': '演示员B',
			'recon': [
				('侦察无人机2', '雷达无人机', 10, 40.0, 1.5, 4.0, -12.0, 30.0, 3.0, 0, 0, 0),
				('光电侦察2', '光电无人机', 6, 25.0, 1.0, 3.8, -8.0, 28.0, 0.5, 0, 0, 0),
			],
			'command': [
				('机动指挥车', 5, 32.0, 3.0, -18.0, 25.0, 0.6, 0, 0, 0),
			],
			'fire': [
				('火箭炮1', '火箭炮', '火箭弹', 25.0, 8.0, -28.0, 18.0, 0.6, 0, 0, 0),
				('导弹发射车1', '导弹发射车', '导弹', 35.0, 7.0, -32.0, 20.0, 0.5, 0, 0, 0),
			],
			'targets': [
				# 单动目标：vx=-2.5, vy=1 (向左上方移动)
				('敌方车队', '车队/纵列', 2, 35.0, 20.0, 0.0, -2.5, 1.0, 0),
			]
		},
		{
			'name': '动目标单方案三-打击指挥所',
			'creator': '演示员C',
			'recon': [
				('高空侦察3', '雷达无人机', 12, 45.0, 1.6, 3.5, -5.0, 35.0, 4.0, 0, 0, 0),
				('地面监听3', '声学侦察', 15, 15.0, 2.5, 2.2, -2.0, 32.0, 0.3, 0, 0, 0),
			],
			'command': [
				('战术指挥中心', 8, 38.0, 2.8, -10.0, 28.0, 1.0, 0, 0, 0),
			],
			'fire': [
				('精确打击导弹', '导弹发射车', '导弹', 40.0, 8.0, -25.0, 22.0, 0.5, 0, 0, 0),
				('攻击无人机1', '攻击无人机', '精确制导炸弹', 20.0, 3.5, -20.0, 25.0, 2.0, 0, 0, 0),
			],
			'targets': [
				# 单动目标：vx=2, vy=-1.5 (向右下方移动)
				('敌方指挥所', '指挥所/坚固点', 4, 10.0, 38.0, 0.0, 2.0, -1.5, 0),
			]
		},
		{
			'name': '动目标单方案四-摧毁炮兵',
			'creator': '演示员D',
			'recon': [
				('反炮兵雷达', '地面雷达', 25, 35.0, 2.0, 1.2, -8.0, 32.0, 1.0, 0, 0, 0),
				('前沿观察哨', '光电无人机', 6, 20.0, 1.1, 4.0, -5.0, 30.0, 0.5, 0, 0, 0),
			],
			'command': [
				('火力协调中心', 7, 33.0, 3.2, -15.0, 28.0, 0.9, 0, 0, 0),
			],
			'fire': [
				('压制火炮', '火炮', '榴弹炮', 30.0, 6.5, -28.0, 20.0, 0.4, 0, 0, 0),
				('火箭压制', '火箭炮', '火箭弹', 28.0, 8.5, -22.0, 18.0, 0.6, 0, 0, 0),
			],
			'targets': [
				# 单动目标：vx=-2, vy=-1 (向左下方移动)
				('敌方炮兵阵地', '炮兵阵地', 4, 30.0, 35.0, 0.0, -2.0, -1.0, 0),
			]
		},
		{
			'name': '动目标单方案五-突袭机场',
			'creator': '演示员E',
			'recon': [
				('卫星侦察5', '卫星侦察', 50, 50.0, 1.8, 2.0, -2.0, 38.0, 6.0, 0, 0, 0),
				('高空侦察5', '雷达无人机', 12, 42.0, 1.5, 3.8, 0.0, 35.0, 3.5, 0, 0, 0),
			],
			'command': [
				('空地协调中心', 6, 36.0, 3.0, -8.0, 30.0, 1.0, 0, 0, 0),
			],
			'fire': [
				('巡航导弹', '导弹发射车', '导弹', 55.0, 8.5, -20.0, 25.0, 0.5, 0, 0, 0),
				('空袭编队', '攻击无人机', '精确制导炸弹', 25.0, 3.2, -15.0, 28.0, 2.0, 0, 0, 0),
			],
			'targets': [
				# 单动目标：vx=1, vy=2.5 (快速向上移动)
				('敌方机动机场', '机场设施', 5, 5.0, 25.0, 0.0, 1.0, 2.5, 0),
			]
		},
	]


def _insert_scheme_nodes(cursor, scheme_id, scheme):
	"""插入方案的所有节点"""
	# 侦察节点
	recon_nodes = [
		(scheme_id, *node) for node in scheme['recon']
	]
	
	# 指挥节点
	command_nodes = [
		(scheme_id, *node) for node in scheme['command']
	]
	
	# 火力节点
	fire_nodes = [
		(scheme_id, *node) for node in scheme['fire']
	]
	
	# 目标节点（包含速度字段 vx, vy, vh）
	target_nodes = [
		(scheme_id, *node) for node in scheme['targets']
	]
	
	# 批量插入
	if recon_nodes:
		cursor.executemany("""
			INSERT INTO reconnaissance_nodes 
			(scheme_id, node_name, model, parallel_limit, recon_range, recon_precision, processing_time, x, y, h, vx, vy, vh)
			VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
		""", recon_nodes)
	
	if command_nodes:
		cursor.executemany("""
			INSERT INTO command_nodes 
			(scheme_id, node_name, command_capacity, comm_distance, processing_time, x, y, h, vx, vy, vh)
			VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
		""", command_nodes)
	
	if fire_nodes:
		cursor.executemany("""
			INSERT INTO firepower_nodes 
			(scheme_id, node_name, firepower_type, ammo_type, comm_distance, processing_time, x, y, h, vx, vy, vh)
			VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
		""", fire_nodes)
	
	if target_nodes:
		cursor.executemany("""
			INSERT INTO target_nodes 
			(scheme_id, node_name, target_type, threat_level, x, y, h, vx, vy, vh)
			VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
		""", target_nodes)


if __name__ == "__main__":
	# 创建数据库和表结构（包含动目标测试方案）
	create_database_and_tables(DATABASE_CONFIG, test_mode=True)
	print("数据库 ssl_3 及所有表已创建（包含10个动目标方案：5个多目标方案和5个单目标方案）。")
