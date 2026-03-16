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
	若 test_mode=True，则会自动写入多套测试方案数据（营级/团级/旅级等）。
	
	参数：
		db_config: 数据库配置字典
		test_mode: 是否启用测试模式（默认 True）
	"""

	# 单次连接：先创建数据库，再切换到该库执行后续操作
	# 这里使用的是“裸连接”，因为此时数据库可能尚未创建，无法直接指定 schema。
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
		# MySQL 在首次连接时默认使用 `mysql` 数据库，这里显式创建目标库，防止重复运行报错。
		cur.execute(
			f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
			"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
		)
	conn.select_db(db_name)
	try:
		with conn.cursor() as cur:
			# 先删除所有表以避免结构冲突
			# 在测试模式下会重复执行脚本，因此先 drop 确保表结构和约束完全按脚本定义。
			if test_mode:
				cur.execute("DROP TABLE IF EXISTS `scheme_master`")
			cur.execute("DROP TABLE IF EXISTS `fire_target_preference`")
			cur.execute("DROP TABLE IF EXISTS `firepower_nodes`")
			cur.execute("DROP TABLE IF EXISTS `target_nodes`")
			cur.execute("DROP TABLE IF EXISTS `command_nodes`")
			cur.execute("DROP TABLE IF EXISTS `reconnaissance_nodes`")
			cur.execute("DROP TABLE IF EXISTS `ammo_data`")
			
			# 测试模式：创建方案主表
			# scheme_master 控制“方案”维度，支持批量插入不同战场场景，便于切换数据。
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
			# 保存不同弹药的性能参数，供后续算法进行成本、反应时间等指标计算。
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
			# 在测试模式下，每条节点记录会附带一个 scheme_id，以便区分不同方案的节点集。
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
			# 指挥节点在多目标模式下需要记录指挥容量，只有在测试模式才会开启该虚拟字段。
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
			# 火力节点保存射程、通信距离等信息，供算法判断可达性和响应时间。
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
			# 目标节点记录威胁度等指标，是多目标调度与评估的核心数据来源。
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
			# 通过弹目偏好矩阵驱动算法倾向于更合理的配对，例如导弹优先攻击高价值目标。
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
			# 该数据集覆盖不同成本、射程、反应时间的典型弹药，便于测试算法的多样性。
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
				# executemany 能够一次性写入多行数据，效率远高于逐条 INSERT。
				"""
				INSERT INTO ammo_data (ammo_type, precision_value, ammo_count, max_range, damage_radius, conversion_coeff, flight_time, cost)
				VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
				""",
				ammo_data
			)

			# 插入弹目偏好表初始数据
			# preference_rank 数值越小权重越大，体现火力平台对不同目标的消灭优先级。
			preference_data = [
				# 导弹发射车偏好
				('导弹发射车', '主战坦克', 1),
				('导弹发射车', '指挥所/坚固点', 2),
				('导弹发射车', '车队/纵列', 2),
				('导弹发射车', '轻步兵/散兵', 3),
				('导弹发射车', '装甲运兵车', 2),
				('导弹发射车', '炮兵阵地', 2),
				('导弹发射车', '雷达站', 1),
				('导弹发射车', '机场设施', 1),
				('导弹发射车', '通信中心', 1),
				# 火炮偏好
				('火炮', '主战坦克', 3),
				('火炮', '指挥所/坚固点', 2),
				('火炮', '车队/纵列', 1),
				('火炮', '轻步兵/散兵', 2),
				('火炮', '装甲运兵车', 2),
				('火炮', '炮兵阵地', 1),
				('火炮', '雷达站', 3),
				('火炮', '机场设施', 2),
				('火炮', '通信中心', 2),
				# 反坦克导弹车偏好
				('反坦克导弹车', '主战坦克', 1),
				('反坦克导弹车', '指挥所/坚固点', 3),
				('反坦克导弹车', '车队/纵列', 2),
				('反坦克导弹车', '轻步兵/散兵', 4),
				('反坦克导弹车', '装甲运兵车', 1),
				('反坦克导弹车', '炮兵阵地', 3),
				('反坦克导弹车', '雷达站', 4),
				('反坦克导弹车', '机场设施', 3),
				('反坦克导弹车', '通信中心', 3),
				# 防空导弹车偏好
				('防空导弹车', '主战坦克', 4),
				('防空导弹车', '指挥所/坚固点', 3),
				('防空导弹车', '车队/纵列', 3),
				('防空导弹车', '轻步兵/散兵', 2),
				('防空导弹车', '装甲运兵车', 4),
				('防空导弹车', '炮兵阵地', 3),
				('防空导弹车', '雷达站', 2),
				('防空导弹车', '机场设施', 1),
				('防空导弹车', '通信中心', 2),
				# 火箭炮偏好
				('火箭炮', '主战坦克', 3),
				('火箭炮', '指挥所/坚固点', 2),
				('火箭炮', '车队/纵列', 1),
				('火箭炮', '轻步兵/散兵', 1),
				('火箭炮', '装甲运兵车', 2),
				('火箭炮', '炮兵阵地', 1),
				('火箭炮', '雷达站', 3),
				('火箭炮', '机场设施', 2),
				('火箭炮', '通信中心', 2),
				# 迫击炮偏好
				('迫击炮', '主战坦克', 4),
				('迫击炮', '指挥所/坚固点', 3),
				('迫击炮', '车队/纵列', 2),
				('迫击炮', '轻步兵/散兵', 1),
				('迫击炮', '装甲运兵车', 3),
				('迫击炮', '炮兵阵地', 2),
				('迫击炮', '雷达站', 4),
				('迫击炮', '机场设施', 3),
				('迫击炮', '通信中心', 3),
				# 狙击手偏好
				('狙击手', '主战坦克', 4),
				('狙击手', '指挥所/坚固点', 2),
				('狙击手', '车队/纵列', 3),
				('狙击手', '轻步兵/散兵', 1),
				('狙击手', '装甲运兵车', 4),
				('狙击手', '炮兵阵地', 3),
				('狙击手', '雷达站', 2),
				('狙击手', '机场设施', 4),
				('狙击手', '通信中心', 2),
				# 攻击无人机偏好
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
				# 保持火力类型 + 目标类型唯一，可以在算法侧直接用 (fire_type, target_type) 作为查找键。
				"""
				INSERT INTO `fire_target_preference` (fire_type, target_type, preference_rank)
				VALUES (%s, %s, %s)
				""",
				preference_data
			)

			# 插入测试数据（包含多个方案）
			# 有了前置基础数据之后，继续生成大量方案节点，方便 UI 直接加载演示数据。
			if test_mode:
				_insert_test_data(cur)

	finally:
		conn.close()


def _insert_test_data(cursor):
	"""插入测试数据：8个场景化多目标方案和5个单目标演示方案"""
	# 采用明确的 created_time 阶梯，保证列表展示时多目标与单目标分组顺序稳定。
	base_time = datetime.now()
	multi_base_time = base_time - timedelta(minutes=5)
	_insert_multi_target_scenarios(cursor, multi_base_time)
	
	# 添加单目标节点演示方案（5个，按节点总数区分）
	single_base_time = base_time
	_insert_single_target_demo_schemes(cursor, single_base_time)


def _insert_multi_target_scenarios(cursor, base_time: datetime):
	"""插入8个手工场景化多目标方案。"""
	scenarios = _get_multi_target_scenarios()
	# 每套方案都内置多条侦察、指挥、火力、目标节点，通过随机抖动构造更真实的位置分布。
	for idx, scenario in enumerate(scenarios):
		scheme_id = str(uuid.uuid4())
		created_time = base_time + timedelta(seconds=idx)  # 多目标分组时间略早
		cursor.execute("""
			INSERT INTO scheme_master (scheme_id, scheme_name, creator, created_time)
			VALUES (%s, %s, %s, %s)
		""", (scheme_id, scenario['name'], scenario['creator'], created_time))
		
		# 通过 `_apply_node_jitter` 为不同节点添加轻微偏移，防止所有方案节点完全重合。
		recon_entries = _apply_node_jitter(scenario['recon'], 1.6, 1.4, 1.5)
		command_entries = _apply_node_jitter(scenario['command'], 0.9, 0.9, 0.7)
		fire_entries = _apply_node_jitter(scenario['fire'], 1.3, 1.2, 1.0)
		target_entries = _apply_node_jitter(scenario['targets'], 1.0, 1.0, 0.8)
		
		recon_nodes = [
			(
				scheme_id,
				node_name,
				model,
				parallel_limit,
				recon_range,
				recon_precision,
				processing_time,
				x, y, h, 0, 0, 0
			)
			for (node_name, model, parallel_limit, recon_range, recon_precision, processing_time, x, y, h)
			in recon_entries
		]
		
		command_nodes = [
			(
				scheme_id,
				node_name,
				command_capacity,
				comm_distance,
				processing_time,
				x, y, h, 0, 0, 0
			)
			for (node_name, command_capacity, comm_distance, processing_time, x, y, h)
			in command_entries
		]
		
		fire_nodes = [
			(
				scheme_id,
				node_name,
				fire_type,
				ammo_type,
				comm_distance,
				processing_time,
				x, y, h, 0, 0, 0
			)
			for (node_name, fire_type, ammo_type, comm_distance, processing_time, x, y, h)
			in fire_entries
		]
		
		target_nodes = [
			(
				scheme_id,
				node_name,
				target_type,
				threat_level,
				x, y, h, 0, 0, 0
			)
			for (node_name, target_type, threat_level, x, y, h)
			in target_entries
		]
		
		# 分四类节点批量写入，提高效率并保持事务一致性。
		_insert_nodes_batch(cursor, recon_nodes, command_nodes, fire_nodes, target_nodes)


def _get_multi_target_scenarios():
	"""构建多目标方案库，每套方案代表一种典型战场情景。"""
	return [{'command': [('沿岸联指A', 8, 18.0, 3.2, 18.5, 30.8, 1.0),
	              ('机动指挥A', 6, 15.5, 3.8, 17.2, 29.5, 0.6),
	              ('预备指挥A', 5, 13.0, 4.1, 16.8, 32.0, 0.6)],
	  'creator': '张三',
	  'fire': [('岸防导弹A', '导弹发射车', '导弹', 24.0, 7.5, 10.2, 30.6, 0.5),
	           ('野战火炮A', '火炮', '榴弹炮', 20.0, 6.8, 9.1, 28.5, 0.4),
	           ('火箭炮旅A', '火箭炮', '火箭弹', 22.0, 9.0, 10.8, 26.8, 0.5),
	           ('机动反坦克A', '反坦克导弹车', '反坦克导弹', 16.5, 5.5, 8.5, 27.9, 0.6),
	           ('无人机打击A', '攻击无人机', '精确制导炸弹', 15.0, 3.5, 9.3, 29.8, 2.5),
	           ('迫击炮阵A', '迫击炮', '迫击炮', 12.0, 5.0, 8.8, 25.6, 0.3)],
	  'name': '方案一-沿海梯次防御',
	  'recon': [('梯次卫星A', '卫星侦察', 40, 24.0, 1.8, 2.5, 25.8, 33.6, 5.0),
	            ('沿岸雷达A', '地面雷达', 20, 12.0, 2.4, 1.0, 24.2, 32.0, 1.2),
	            ('沿岸光电A', '光电无人机', 6, 10.5, 1.2, 4.8, 23.7, 30.2, 0.5),
	            ('山地哨所A', '地面雷达', 18, 11.0, 2.1, 1.2, 24.8, 34.2, 1.1),
	            ('高空雷达A', '雷达无人机', 12, 14.0, 1.6, 4.0, 24.5, 31.0, 3.0)],
	  'targets': [('敌海岸炮位A', '炮兵阵地', 3, 34.8, 33.2, 0.5),
	              ('敌指控节点A', '通信中心', 4, 35.6, 32.0, 1.0),
	              ('敌机场A', '机场设施', 5, 36.4, 34.0, 0.0),
	              ('敌装甲纵队A', '主战坦克', 3, 33.5, 30.2, 0.0),
	              ('敌补给点A', '车队/纵列', 2, 32.8, 31.6, 0.0),
	              ('敌防空A', '防空阵地', 4, 35.0, 29.5, 0.0)]},
	 {'command': [('都市联指U', 8, 17.0, 3.3, 17.0, 27.2, 1.0),
	              ('机动指挥U', 6, 14.5, 3.6, 15.8, 25.5, 0.6),
	              ('空地协调U', 5, 15.0, 3.4, 16.5, 28.0, 1.2)],
	  'creator': '李四',
	  'fire': [('城市防空U', '防空导弹车', '防空导弹', 19.0, 4.8, 9.5, 28.0, 0.8),
	           ('重炮阵地U', '火炮', '榴弹炮', 18.5, 6.5, 8.2, 26.0, 0.5),
	           ('火箭支援U', '火箭炮', '火箭弹', 20.0, 8.0, 10.0, 24.5, 0.7),
	           ('机动反坦克U', '反坦克导弹车', '反坦克导弹', 15.0, 5.0, 7.8, 23.8, 0.5),
	           ('无人机打击U', '攻击无人机', '精确制导炸弹', 14.0, 3.2, 9.0, 25.5, 2.0),
	           ('迫击阵地U', '迫击炮', '迫击炮', 11.0, 4.6, 8.8, 22.5, 0.3)],
	  'name': '方案二-城市纵深封锁',
	  'recon': [('城区卫星U', '卫星侦察', 40, 22.0, 1.7, 2.2, 24.8, 27.5, 5.5),
	            ('城区雷达U', '地面雷达', 18, 11.5, 2.2, 1.1, 23.0, 26.5, 1.1),
	            ('城区光电U', '光电无人机', 6, 9.0, 1.0, 4.2, 22.5, 24.8, 0.6),
	            ('监听分队U', '声学侦察', 10, 6.5, 2.6, 2.2, 23.5, 25.8, 0.3),
	            ('高空雷达U', '雷达无人机', 12, 14.0, 1.6, 3.4, 24.0, 28.8, 4.0)],
	  'targets': [('敌通信塔U', '通信中心', 3, 31.2, 27.5, 0.0),
	              ('敌指挥楼U', '指挥所/坚固点', 4, 32.0, 26.2, 0.0),
	              ('敌机场跑道U', '机场设施', 5, 33.5, 28.5, 0.0),
	              ('敌装甲突击U', '主战坦克', 3, 30.5, 24.8, 0.0),
	              ('敌防空阵地U', '防空阵地', 4, 31.8, 29.2, 0.0),
	              ('敌补给仓储U', '车队/纵列', 2, 30.2, 25.8, 0.0)]},
	 {'command': [('山前联指M', 7, 17.0, 3.2, 17.8, 30.5, 1.0),
	              ('高机动指挥M', 6, 15.0, 3.5, 16.5, 28.8, 0.8),
	              ('旅前指挥M', 5, 13.0, 3.8, 17.0, 32.0, 0.7)],
	  'creator': '王五',
	  'fire': [('高原导弹M', '导弹发射车', '导弹', 24.0, 7.8, 10.5, 31.0, 0.6),
	           ('山地火炮M', '火炮', '榴弹炮', 19.0, 6.4, 9.0, 29.0, 0.5),
	           ('火箭炮M', '火箭炮', '火箭弹', 21.0, 8.5, 10.2, 27.5, 0.7),
	           ('反坦克伏击M', '反坦克导弹车', '反坦克导弹', 15.5, 5.2, 8.2, 26.5, 0.4),
	           ('无人机打击M', '攻击无人机', '精确制导炸弹', 14.5, 3.4, 9.5, 28.2, 2.0),
	           ('迫击阵地M', '迫击炮', '迫击炮', 11.5, 4.8, 8.0, 25.2, 0.3)],
	  'name': '方案三-山谷楔形突击',
	  'recon': [('山谷卫星M', '卫星侦察', 45, 23.0, 1.7, 2.0, 26.5, 31.5, 6.5),
	            ('山口雷达M', '地面雷达', 22, 11.5, 2.2, 1.1, 25.0, 30.0, 1.5),
	            ('峡谷雷达M', '地面雷达', 20, 10.8, 2.0, 1.0, 24.2, 28.5, 1.2),
	            ('高空无人M', '雷达无人机', 12, 14.0, 1.6, 4.0, 25.5, 32.0, 3.5),
	            ('山口光电M', '光电无人机', 6, 9.5, 1.1, 4.5, 23.5, 29.2, 0.6),
	            ('前沿侦听M', '声学侦察', 10, 6.2, 2.7, 2.0, 22.8, 27.8, 0.4)],
	  'targets': [('敌山口防空M', '防空阵地', 4, 33.0, 31.5, 0.0),
	              ('敌山谷指挥M', '指挥所/坚固点', 4, 34.0, 30.2, 0.0),
	              ('敌补给洞库M', '通信中心', 3, 32.5, 28.0, 0.0),
	              ('敌装甲穿插M', '装甲运兵车', 3, 31.0, 27.0, 0.0),
	              ('敌远程火力M', '炮兵阵地', 4, 34.5, 32.5, 0.0)]},
	 {'command': [('沙漠联指D', 8, 18.0, 3.0, 17.2, 26.8, 0.8),
	              ('机动指挥D', 6, 15.0, 3.4, 16.0, 25.0, 0.6),
	              ('空地协调D', 5, 14.0, 3.2, 17.8, 28.0, 1.0)],
	  'creator': '赵六',
	  'fire': [('远程导弹D', '导弹发射车', '导弹', 25.0, 8.0, 10.8, 27.5, 0.5),
	           ('重炮营D', '火炮', '榴弹炮', 20.0, 6.2, 9.5, 26.0, 0.4),
	           ('火箭营D', '火箭炮', '火箭弹', 22.0, 8.7, 11.2, 24.8, 0.6),
	           ('机动反坦克D', '反坦克导弹车', '反坦克导弹', 16.5, 5.0, 8.5, 24.0, 0.4),
	           ('迫击炮D', '迫击炮', '迫击炮', 12.0, 4.8, 9.0, 22.5, 0.3),
	           ('无人打击D', '攻击无人机', '精确制导炸弹', 15.0, 3.3, 9.8, 23.8, 2.0)],
	  'name': '方案四-沙漠列阵截击',
	  'recon': [('沙漠卫星D', '卫星侦察', 45, 24.0, 1.7, 2.1, 25.2, 27.5, 6.0),
	            ('长航无人D', '雷达无人机', 12, 15.0, 1.5, 3.5, 24.0, 26.0, 3.0),
	            ('机动雷达D', '地面雷达', 20, 11.0, 2.0, 1.2, 22.5, 25.0, 1.0),
	            ('前沿监听D', '声学侦察', 12, 6.5, 2.6, 2.0, 23.0, 24.0, 0.4),
	            ('低空光电D', '光电无人机', 6, 9.5, 1.1, 4.3, 24.5, 25.8, 0.6)],
	  'targets': [('敌补给枢纽D', '车队/纵列', 3, 31.0, 27.8, 0.0),
	              ('敌油料库D', '通信中心', 3, 32.2, 26.5, 0.0),
	              ('敌沙漠机场D', '机场设施', 5, 33.5, 28.5, 0.0),
	              ('敌装甲掩体D', '主战坦克', 3, 30.5, 25.0, 0.0),
	              ('敌远程火力D', '炮兵阵地', 4, 34.0, 27.2, 0.0)]},
	 {'command': [('沿海联指I', 8, 18.5, 3.1, 17.5, 30.8, 1.0),
	              ('两栖指挥I', 6, 16.0, 3.6, 16.2, 28.8, 0.8),
	              ('空海协调I', 6, 15.0, 3.2, 17.0, 32.0, 0.9)],
	  'creator': '钱七',
	  'fire': [('岸防导弹I', '导弹发射车', '导弹', 24.5, 7.6, 10.2, 31.0, 0.5),
	           ('舰炮支援I', '火炮', '榴弹炮', 19.5, 6.5, 9.0, 29.0, 0.4),
	           ('远程火箭I', '火箭炮', '火箭弹', 22.0, 8.5, 11.0, 27.5, 0.6),
	           ('直升机打击I', '攻击无人机', '精确制导炸弹', 15.0, 3.3, 8.5, 26.0, 2.3),
	           ('机动反舰I', '反坦克导弹车', '反坦克导弹', 17.0, 5.0, 9.8, 25.0, 0.5),
	           ('迫击阵地I', '迫击炮', '迫击炮', 12.5, 4.8, 8.2, 24.0, 0.3)],
	  'name': '方案五-岛链阻击阵',
	  'recon': [('岛链卫星I', '卫星侦察', 45, 25.0, 1.8, 2.0, 25.5, 31.0, 5.5),
	            ('远岸雷达I', '地面雷达', 22, 12.0, 2.2, 1.1, 24.2, 29.8, 1.3),
	            ('岛屿光电I', '光电无人机', 6, 10.0, 1.1, 4.8, 23.0, 28.5, 0.6),
	            ('舰载无人I', '雷达无人机', 12, 14.5, 1.5, 3.8, 24.8, 31.5, 3.0),
	            ('沿岸声侦I', '声学侦察', 10, 6.2, 2.7, 2.2, 23.5, 27.5, 0.4)],
	  'targets': [('敌登陆舰队I', '车队/纵列', 3, 32.5, 31.0, 0.0),
	              ('敌临时指挥I', '指挥所/坚固点', 4, 33.8, 29.8, 0.0),
	              ('敌海岸炮I', '炮兵阵地', 4, 35.0, 31.8, 0.0),
	              ('敌机场跑道I', '机场设施', 5, 36.0, 33.2, 0.0),
	              ('敌防空节点I', '防空阵地', 4, 33.0, 28.5, 0.0)]},
	 {'command': [('高原防空指挥H', 9, 20.0, 3.5, 18.2, 32.0, 1.2),
	              ('机动指挥H', 6, 16.5, 3.3, 17.0, 30.0, 0.9),
	              ('空防协调H', 6, 15.0, 3.2, 17.8, 33.0, 1.0)],
	  'creator': '孙八',
	  'fire': [('远程导弹H', '导弹发射车', '导弹', 26.0, 8.0, 11.2, 33.2, 0.6),
	           ('重炮群H', '火炮', '榴弹炮', 20.5, 6.6, 10.0, 31.0, 0.5),
	           ('火箭旅H', '火箭炮', '火箭弹', 22.5, 8.6, 11.8, 29.5, 0.7),
	           ('防空导弹H', '防空导弹车', '防空导弹', 19.0, 5.0, 10.5, 28.0, 0.8),
	           ('无人打击H', '攻击无人机', '精确制导炸弹', 15.5, 3.3, 9.0, 30.0, 2.2),
	           ('反坦克机动H', '反坦克导弹车', '反坦克导弹', 16.0, 5.1, 9.8, 27.2, 0.5),
	           ('迫击炮H', '迫击炮', '迫击炮', 12.0, 4.9, 8.8, 26.0, 0.3)],
	  'name': '方案六-高原屏障防空',
	  'recon': [('高原卫星H', '卫星侦察', 50, 23.5, 1.7, 2.0, 26.2, 33.5, 7.0),
	            ('高原雷达H', '地面雷达', 24, 12.5, 2.3, 1.1, 25.0, 32.0, 2.0),
	            ('高空无人H', '雷达无人机', 12, 15.0, 1.5, 3.6, 24.0, 30.5, 3.8),
	            ('山前雷达H', '地面雷达', 22, 11.0, 2.1, 1.0, 24.5, 34.2, 1.5),
	            ('红外侦察H', '光电无人机', 6, 9.8, 1.1, 4.4, 23.2, 29.5, 0.6),
	            ('前沿监听H', '声学侦察', 12, 6.3, 2.6, 2.1, 22.5, 28.2, 0.4)],
	  'targets': [('敌高原雷达H', '雷达站', 4, 34.2, 33.5, 0.0),
	              ('敌指挥洞室H', '指挥所/坚固点', 4, 35.5, 32.0, 0.0),
	              ('敌远程炮阵H', '炮兵阵地', 4, 36.2, 34.5, 0.0),
	              ('敌防空阵地H', '防空阵地', 4, 34.8, 30.8, 0.0),
	              ('敌机场H', '机场设施', 5, 37.0, 33.0, 0.0),
	              ('敌补给站H', '通信中心', 3, 33.5, 29.5, 0.0)]},
	 {'command': [('集团军指挥B', 10, 22.0, 3.0, 18.5, 33.0, 1.5),
	              ('空地协调B', 7, 16.5, 2.8, 17.0, 31.0, 1.0),
	              ('快速指挥B', 6, 14.0, 3.5, 17.8, 34.0, 0.5)],
	  'creator': '周八',
	  'fire': [('远程导弹B', '导弹发射车', '导弹', 25.0, 8.5, 10.8, 34.2, 0.5),
	           ('重炮营B', '火炮', '榴弹炮', 21.0, 6.5, 9.5, 32.0, 0.4),
	           ('火箭炮B', '火箭炮', '火箭弹', 23.0, 8.8, 11.5, 30.5, 0.6),
	           ('反装甲B', '反坦克导弹车', '反坦克导弹', 17.0, 5.2, 9.0, 29.0, 0.5),
	           ('攻击无人机B', '攻击无人机', '精确制导炸弹', 16.0, 3.2, 10.2, 31.5, 2.0),
	           ('防空打击B', '防空导弹车', '防空导弹', 18.0, 4.8, 9.5, 28.0, 0.8),
	           ('迫击群B', '迫击炮', '迫击炮', 11.0, 4.5, 8.5, 27.0, 0.3)],
	  'name': '方案七-纵深扇形围歼',
	  'recon': [('高空雷达B', '雷达无人机', 14, 15.0, 1.5, 3.5, 26.5, 34.5, 4.5),
	            ('低空光电B', '光电无人机', 6, 9.5, 1.1, 4.5, 25.0, 33.0, 0.6),
	            ('地面雷达B1', '地面雷达', 25, 10.0, 2.0, 1.2, 24.0, 32.2, 0.8),
	            ('地面雷达B2', '地面雷达', 25, 11.5, 2.2, 1.1, 25.8, 31.0, 0.8),
	            ('声学侦察B', '声学侦察', 10, 6.0, 2.8, 2.0, 23.5, 30.0, 0.4),
	            ('卫星侦察B', '卫星侦察', 50, 22.0, 1.9, 2.0, 27.0, 35.8, 6.0)],
	  'targets': [('敌装甲指挥B', '指挥所/坚固点', 4, 34.8, 34.0, 0.0),
	              ('敌机动补给B', '车队/纵列', 3, 35.5, 32.0, 0.0),
	              ('敌长程火力B', '炮兵阵地', 4, 36.5, 33.5, 0.0),
	              ('敌防空阵地B', '防空阵地', 4, 33.5, 31.0, 0.0),
	              ('敌机场节点B', '机场设施', 5, 37.0, 34.8, 0.0),
	              ('敌通信枢纽B', '通信中心', 3, 33.2, 29.5, 0.0),
	              ('敌装步集群B', '装甲运兵车', 3, 32.0, 28.8, 0.0)]},
	 {'command': [('渡口联指R', 8, 17.5, 3.1, 17.0, 30.0, 1.0),
	              ('应急指挥R', 6, 15.0, 3.4, 16.0, 28.2, 0.7),
	              ('火力协调R', 5, 14.0, 3.2, 17.5, 31.5, 0.9)],
	  'creator': '吴九',
	  'fire': [('远程导弹R', '导弹发射车', '导弹', 24.0, 7.8, 10.0, 30.8, 0.5),
	           ('重炮群R', '火炮', '榴弹炮', 19.0, 6.4, 8.8, 29.0, 0.4),
	           ('火箭营R', '火箭炮', '火箭弹', 21.5, 8.5, 11.2, 27.2, 0.6),
	           ('反坦克R', '反坦克导弹车', '反坦克导弹', 15.5, 5.1, 8.2, 26.0, 0.4),
	           ('无人机R', '攻击无人机', '精确制导炸弹', 14.5, 3.3, 9.5, 28.0, 2.0),
	           ('迫击阵地R', '迫击炮', '迫击炮', 11.5, 4.7, 8.5, 25.0, 0.3)],
	  'name': '方案八-渡口拦截网',
	  'recon': [('河段卫星R', '卫星侦察', 45, 22.0, 1.8, 2.1, 24.2, 30.5, 5.5),
	            ('河岸雷达R', '地面雷达', 20, 11.5, 2.2, 1.1, 23.0, 29.5, 1.2),
	            ('桥头光电R', '光电无人机', 6, 9.8, 1.0, 4.5, 22.0, 28.2, 0.5),
	            ('防渡无人R', '雷达无人机', 12, 14.0, 1.5, 3.6, 23.5, 31.0, 3.0),
	            ('前沿监听R', '声学侦察', 10, 6.4, 2.6, 2.1, 21.8, 27.5, 0.3)],
	  'targets': [('敌浮桥R', '车队/纵列', 3, 31.8, 31.0, 0.0),
	              ('敌渡桥指挥R', '指挥所/坚固点', 4, 33.0, 29.8, 0.0),
	              ('敌防空掩护R', '防空阵地', 4, 34.0, 31.2, 0.0),
	              ('敌集结场R', '主战坦克', 3, 32.5, 28.5, 0.0),
	              ('敌后方炮阵R', '炮兵阵地', 4, 35.2, 30.5, 0.0)]}]


def _apply_node_jitter(entries, x_jitter, y_jitter, radial_jitter=0.0):
	"""为节点坐标添加轻微扰动与径向散布，避免出现完全整齐的排列。"""
	if x_jitter <= 0 and y_jitter <= 0 and radial_jitter <= 0:
		return entries
	jittered = []
	for entry in entries:
		head = entry[:-3]
		x, y, h = entry[-3:]
		# 先生成轴向扰动，再叠加随机方向的径向扰动，使点云分布更自然。
		dx = random.uniform(-x_jitter, x_jitter) if x_jitter else 0
		dy = random.uniform(-y_jitter, y_jitter) if y_jitter else 0
		if radial_jitter > 0:
			radius = random.uniform(0, radial_jitter)
			theta = random.uniform(0, 2 * math.pi)
			dx += math.cos(theta) * radius
			dy += math.sin(theta) * radius
		new_x = round(x + dx, 2)
		new_y = round(y + dy, 2)
		jittered.append((*head, new_x, new_y, h))
	return jittered


def _insert_nodes_batch(cursor, recon_nodes, command_nodes, fire_nodes, target_nodes):
	"""批量插入节点数据"""
	# executemany 顺序固定：侦察 -> 指挥 -> 火力 -> 目标，与 UI 展示顺序保持一致。
	cursor.executemany("""
		INSERT INTO reconnaissance_nodes (scheme_id, node_name, model, parallel_limit, recon_range, recon_precision, processing_time, x, y, h, vx, vy, vh)
		VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
	""", recon_nodes)
	cursor.executemany("""
		INSERT INTO command_nodes (scheme_id, node_name, command_capacity, comm_distance, processing_time, x, y, h, vx, vy, vh)
		VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
	""", command_nodes)
	cursor.executemany("""
		INSERT INTO firepower_nodes (scheme_id, node_name, firepower_type, ammo_type, comm_distance, processing_time, x, y, h, vx, vy, vh)
		VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
	""", fire_nodes)
	cursor.executemany("""
		INSERT INTO target_nodes (scheme_id, node_name, target_type, threat_level, x, y, h, vx, vy, vh)
		VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
	""", target_nodes)


def _generate_recon_nodes_by_count(count, scheme_id):
	"""按指定数量生成侦察节点数据（前线部署）"""
	recon_nodes = []
	recon_types = [
		('光电无人机', 4, (6, 12), (0.8, 1.5), (3, 8)),
		('雷达无人机', 10, (8, 15), (1.2, 2.0), (4, 10)),
		('地面雷达', 30, (5, 12), (3, 8), (0.5, 2)),
		('卫星侦察', 50, (15, 25), (1.5, 3), (1, 3)),
		('红外侦察', 8, (4, 8), (1.0, 2.5), (2, 6)),
		('声学侦察', 15, (3, 6), (2, 5), (1, 4)),
	]
	for i in range(count):
		# 通过 i % len(recon_types) 轮询模板，让任意数量的节点都能复用这套配置。
		type_name, parallel_limit, range_bounds, precision_bounds, time_bounds = recon_types[i % len(recon_types)]
		# 侦察节点位于战场前沿，x/y 坐标集中在正向区域。
		x = round(random.uniform(2, 8), 2)
		y = round(random.uniform(26, 32), 2)
		recon_nodes.append((
			scheme_id,
			f'{type_name}{i+1}',
			type_name,
			parallel_limit,
			round(random.uniform(*range_bounds), 2),
			round(random.uniform(*precision_bounds), 2),
			round(random.uniform(*time_bounds), 2),
			x, y, 0, 0, 0, 0
		))
	return recon_nodes


def _generate_single_recon_nodes(count, scheme_id):
	"""单目标专用侦察节点，位置和射程保证覆盖目标，同时带随机偏移避免全同"""
	recon_nodes = []
	for i in range(count):
		x = round(random.uniform(7.0, 10.0), 2)
		y = round(random.uniform(29.5, 33.5), 2)
		range_val = round(random.uniform(30.0, 36.0), 2)
		recon_nodes.append((
			scheme_id,
			f'单目侦察{i+1}',
			'光电无人机',
			8,
			range_val,  # 足够覆盖前方目标
			round(random.uniform(0.8, 1.6), 2),
			round(random.uniform(2.5, 5.0), 2),
			x, y, 0, 0, 0, 0
		))
	return recon_nodes


def _generate_command_nodes_by_count(count, scheme_id):
	"""按指定数量生成指挥节点数据（纵深部署）"""
	command_nodes = []
	command_types = [
		('主指挥所', (10, 12), (12, 20), (2, 5)),
		('移动指挥车', (3, 5), (8, 15), (1.5, 4)),
		('战术指挥中心', (6, 8), (10, 18), (3, 7)),
		('空中指挥机', (8, 10), (15, 25), (1, 3)),
		('前沿指挥所', (2, 4), (6, 12), (2, 5)),
	]
	for i in range(count):
		type_name, capacity_bounds, comm_bounds, time_bounds = command_types[i % len(command_types)]
		# 指挥节点通常部署在后方，因此 x 坐标大概率为负。
		x = round(random.uniform(-8, -3), 2)
		y = round(random.uniform(20, 26), 2)
		command_nodes.append((
			scheme_id,
			f'{type_name}{i+1}',
			random.randint(*capacity_bounds),
			round(random.uniform(*comm_bounds), 2),
			round(random.uniform(*time_bounds), 2),
			x, y, 0, 0, 0, 0
		))
	return command_nodes


def _generate_single_command_nodes(count, scheme_id):
	"""单目标专用指挥节点，确保可同时联通侦察和火力，并带位置抖动"""
	command_nodes = []
	for i in range(count):
		x = round(random.uniform(-2.5, 3.5), 2)
		y = round(random.uniform(22.0, 28.0), 2)
		comm_val = round(random.uniform(32.0, 38.0), 2)
		command_nodes.append((
			scheme_id,
			f'单目指挥{i+1}',
			8,
			comm_val,  # 保证能覆盖侦察和火力
			round(random.uniform(1.2, 3.5), 2),
			x, y, 0, 0, 0, 0
		))
	return command_nodes


def _generate_firepower_nodes_by_count(count, scheme_id):
	"""按指定数量生成火力节点数据（大后方火力）"""
	firepower_nodes = []
	fire_types = [
		('导弹发射车', '导弹发射车', '导弹', (15, 25), (6, 12)),
		('火炮', '火炮', '榴弹炮', (15, 25), (8, 18)),
		('反坦克导弹车', '反坦克导弹车', '反坦克导弹', (10, 18), (4, 10)),
		('防空导弹车', '防空导弹车', '防空导弹', (12, 20), (5, 10)),
		('火箭炮', '火箭炮', '火箭弹', (12, 20), (10, 20)),
		('迫击炮', '迫击炮', '迫击炮', (8, 15), (5, 12)),
		('狙击手', '狙击手', '子弹', (5, 10), (2, 6)),
		('攻击无人机', '攻击无人机', '精确制导炸弹', (8, 15), (3, 8)),
	]
	for i in range(count):
		type_name, fire_type, ammo_type, comm_bounds, time_bounds = fire_types[i % len(fire_types)]
		# 火力节点离前线更远一些，坐标进一步偏向战场后方。
		x = round(random.uniform(-12, -2), 2)
		y = round(random.uniform(12, 20), 2)
		firepower_nodes.append((
			scheme_id,
			f'{type_name}{i+1}',
			fire_type,
			ammo_type,
			round(random.uniform(*comm_bounds), 2),
			round(random.uniform(*time_bounds), 2),
			x, y, 0, 0, 0, 0
		))
	return firepower_nodes


def _generate_single_firepower_nodes(count, scheme_id):
	"""单目标专用火力节点，位置后置但射程足够到达目标，同时增加多样性"""
	firepower_nodes = []
	for i in range(count):
		x = round(random.uniform(-10.0, -3.0), 2)
		y = round(random.uniform(14.0, 21.0), 2)
		comm_val = round(random.uniform(38.0, 45.0), 2)
		fire_type, ammo_type = random.choice([
			('导弹发射车', '导弹'),
			('反坦克导弹车', '反坦克导弹'),
			('攻击无人机', '精确制导炸弹'),
		])
		firepower_nodes.append((
			scheme_id,
			f'单目火力{i+1}',
			fire_type,
			ammo_type,
			comm_val,  # 覆盖至目标区
			round(random.uniform(6.0, 10.0), 2),
			x, y, 0, 0, 0, 0
		))
	return firepower_nodes


def _generate_target_nodes_by_count(count, scheme_id):
	"""按指定数量生成目标节点数据（敌纵深）"""
	target_nodes = []
	target_types = [
		('敌方坦克', '主战坦克', (1, 2)),
		('敌方指挥所', '指挥所/坚固点', (2, 3)),
		('敌方车队', '车队/纵列', (2, 4)),
		('敌方步兵', '轻步兵/散兵', (3, 5)),
		('敌方装甲车', '装甲运兵车', (2, 3)),
		('敌方炮兵阵地', '炮兵阵地', (2, 4)),
		('敌方雷达站', '雷达站', (3, 4)),
		('敌方机场', '机场设施', (4, 5)),
		('敌方通信中心', '通信中心', (3, 4)),
	]
	for i in range(count):
		name_prefix, target_type, threat_bounds = target_types[i % len(target_types)]
		# 敌方目标分布在纵深区域，x/y 都偏向正向坐标。
		x = round(random.uniform(7, 14), 2)
		y = round(random.uniform(30, 36), 2)
		target_nodes.append((
			scheme_id,
			f'{name_prefix}{i+1}',
			target_type,
			random.randint(*threat_bounds),
			x, y, 0, 0, 0, 0
		))
	return target_nodes


def _insert_single_target_demo_schemes(cursor, base_time: datetime):
	"""插入单目标节点的演示方案（5个，节点数区分为10/20/30/40/50）"""
	# 按节点总量构造五套单目标方案，保持与多目标列表分离，便于界面区分。
	# 每套方案使用不同的空间偏移，避免坐标完全重叠。
	scheme_offsets = [
		(0.0, 0.0),
		(1.2, -0.8),
		(-1.0, 1.0),
		(0.8, 1.5),
		(-1.4, -1.2),
	]
	single_target_definitions = [
		{
			'name': '演示方案六-单目标10节点',
			'creator': '演示员A',
			'target': ('主战坦克', '敌方主战坦克', 1),
			'counts': (3, 2, 4)  # recon, command, fire（再加1个目标=10）
		},
		{
			'name': '演示方案七-单目标20节点',
			'creator': '演示员B',
			'target': ('指挥所/坚固点', '敌方指挥所', 2),
			'counts': (6, 4, 9)  # +1目标=20
		},
		{
			'name': '演示方案八-单目标30节点',
			'creator': '演示员C',
			'target': ('装甲运兵车', '敌方装甲车', 2),
			'counts': (9, 6, 14)  # +1目标=30
		},
		{
			'name': '演示方案九-单目标40节点',
			'creator': '演示员D',
			'target': ('通信中心', '敌方通信中心', 3),
			'counts': (12, 8, 19)  # +1目标=40
		},
		{
			'name': '演示方案十-单目标50节点',
			'creator': '演示员E',
			'target': ('机场设施', '敌方机场', 4),
			'counts': (15, 10, 24)  # +1目标=50
		},
	]
	
	# 插入方案主表，保持单目标方案列表排列独立。
	scheme_master_rows = []
	for idx, scheme in enumerate(single_target_definitions):
		scheme['scheme_id'] = str(uuid.uuid4())
		created_time = base_time + timedelta(seconds=idx)  # 单目标分组时间略晚
		scheme_master_rows.append((scheme['scheme_id'], scheme['name'], scheme['creator'], created_time))
	
	cursor.executemany("""
		INSERT INTO scheme_master (scheme_id, scheme_name, creator, created_time)
		VALUES (%s, %s, %s, %s)
	""", scheme_master_rows)
	
	# 为不同节点规模依次生成数据集
	for idx, scheme in enumerate(single_target_definitions, start=6):
		print(f"  生成演示方案{idx}({scheme['name']})...")
		recon_count, command_count, fire_count = scheme['counts']
		target_type, node_name, threat = scheme['target']
		offset_x, offset_y = scheme_offsets[idx - 6]
		
		def _offset_nodes(nodes_list, offset_x, offset_y):
			return [
				(
					n[0],
					n[1],
					*n[2:-6],
					round(n[-6] + offset_x, 2),
					round(n[-5] + offset_y, 2),
					*n[-4:]
				)
				for n in nodes_list
			]
		
		# 使用单目标专用的节点生成器，保证链路距离可达
		recon_nodes = _offset_nodes(_generate_single_recon_nodes(recon_count, scheme['scheme_id']), offset_x, offset_y)
		command_nodes = _offset_nodes(_generate_single_command_nodes(command_count, scheme['scheme_id']), offset_x, offset_y)
		fire_nodes = _offset_nodes(_generate_single_firepower_nodes(fire_count, scheme['scheme_id']), offset_x, offset_y)
		target_nodes = _generate_single_target_node(scheme['scheme_id'], target_type, node_name, threat)
		_insert_nodes_batch(cursor, recon_nodes, command_nodes, fire_nodes, target_nodes)


def _generate_single_target_node(scheme_id, target_type, node_name, threat_level):
	"""生成单个目标节点"""
	# 单目标演示也需要随机坐标，防止与其它方案出现重复点。
	x = round(random.uniform(7.5, 12.5), 2)
	y = round(random.uniform(31, 37), 2)
	
	return [(
		scheme_id,
		node_name,
		target_type,
		threat_level,
		x, y, 0, 0, 0, 0
	)]


if __name__ == "__main__":
	# 创建数据库和表结构（包含方案管理功能和测试数据）
	create_database_and_tables(DATABASE_CONFIG, test_mode=True)
print("数据库 ssl_3 及所有表已创建/存在（包含13个测试方案：8个场景化多目标方案和5个单目标演示方案）。")
