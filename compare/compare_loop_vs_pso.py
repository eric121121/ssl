"""
单目标遍历算法（loop_method）与粒子群算法（pso_method）对比脚本，可一次对比多个方案。

用法：
    # 指定数据库方案
    python compare_loop_vs_pso.py --scheme-ids <id1> <id2> ...

    # 不传参数时，自动读取数据库中 target 节点数量为 1 的方案（按名称排序，默认取 3 个）
    # 若查询失败或没有单目标方案，会给出提示并退出

    # 每种算法默认重复运行 3 次，取平均耗时和最优指标；可通过 --runs 调整

输出：
    - 控制台：每个方案的耗时与最佳指标
    - 图片：compare/algorithm_compare.png，包含多个方案的柱状对比
"""
import argparse
import matplotlib
import time
import sys
from typing import Optional
from pathlib import Path
import numpy as np
import pandas as pd

RUNS_DEFAULT = 3

# 非交互环境下使用无界面后端，避免弹窗阻塞
matplotlib.use("Agg")

import matplotlib.pyplot as plt

# 设置中文字体，避免图例/坐标轴出现乱码；增加数学字体以保证 σ² 正确渲染
plt.rcParams["font.sans-serif"] = ["SimHei"]  # 或 ["Noto Sans CJK SC"]、["Microsoft YaHei"] 等已安装字体
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["mathtext.fontset"] = "stix"


# 兼容直接在 compare/ 目录执行：把项目根目录加入 sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from algorithms.single_target import loop_method, pso_method
from config import DATABASE_CONFIG
from repositories.mysql_repository import MySQLRepository
from services.node_service import NodeService

# -------------------- 示例数据（取自 data.py 的“论文方案”） --------------------

SAMPLE_AMMO = {
    "火箭弹": {"precision": 30.0, "count": 8, "range": 18.0, "omega": 2.5, "flight_time": 120.0, "cost": 5000.0},
    "巡飞弹": {"precision": 1.5, "count": 16, "range": 60.0, "omega": 1.2, "flight_time": 721.0, "cost": 80000.0},
    "122榴弹炮": {"precision": 10.0, "count": 40, "range": 15.0, "omega": 1.0, "flight_time": 100.0, "cost": 1500.0},
    "坦克炮": {"precision": 2.0, "count": 20, "range": 2.5, "omega": 0.9, "flight_time": 40.0, "cost": 2000.0},
    "红箭-10": {"precision": 2.0, "count": 8, "range": 16.0, "omega": 1.5, "flight_time": 76.0, "cost": 50000.0},
}

SAMPLE_TARGET_A = {"coord": (0.0, 35.0)}
SAMPLE_RECON_A = [
    {"coord": (-5.0, 34.0), "range": 6.0, "sigma2": 1.0, "t_deal": 5.0, "parallel_limit": 1, "model": "侦察"},
    {"coord": (-6.0, 36.0), "range": 5.0, "sigma2": 1.5, "t_deal": 7.0, "parallel_limit": 1, "model": "侦察"},
    {"coord": (-4.0, 37.0), "range": 5.0, "sigma2": 1.2, "t_deal": 6.0, "parallel_limit": 1, "model": "侦察"},
    {"coord": (-5.0, 33.0), "range": 7.0, "sigma2": 1.8, "t_deal": 8.0, "parallel_limit": 1, "model": "侦察"},
]
SAMPLE_COMMAND_A = [
    {"coord": (-10.0, 37.0), "range": 6.0, "t_deal": 4.0, "command_capacity": 3},
    {"coord": (-10.0, 31.0), "range": 5.5, "t_deal": 3.5, "command_capacity": 3},
]
SAMPLE_FIRE_A = [
    {"coord": (-15.0, 36.0), "range": 18.0, "t_deal": 15.0, "ammo_type": "火箭弹", "firepower_type": "火箭弹"},
    {"coord": (-15.0, 35.0), "range": 60.0, "t_deal": 15.0, "ammo_type": "巡飞弹", "firepower_type": "巡飞弹"},
    {"coord": (-14.0, 32.0), "range": 15.0, "t_deal": 3.0, "ammo_type": "122榴弹炮", "firepower_type": "122榴弹炮"},
    {"coord": (-13.0, 38.0), "range": 2.5, "t_deal": 8.0, "ammo_type": "坦克炮", "firepower_type": "坦克炮"},
    {"coord": (-14.0, 30.0), "range": 16.0, "t_deal": 12.0, "ammo_type": "红箭-10", "firepower_type": "红箭-10"},
]

def _make_nodes(target_coord, recon_list, command_list, fire_list):
    """把列表形式的节点数据转换成算法期望的 dict 格式。"""
    nodes = {"target": target_coord, "recon": {}, "command": {}, "fire": {}}
    for i, item in enumerate(recon_list, 1):
        nodes["recon"][f"o{i}"] = {**item}
    for i, item in enumerate(command_list, 1):
        nodes["command"][f"c{i}"] = {**item}
    for i, item in enumerate(fire_list, 1):
        ammo = SAMPLE_AMMO[item["ammo_type"]]
        nodes["fire"][f"w{i}"] = {
            **item,
            "ammo": {
                "count": ammo["count"],
                "omega": ammo["omega"],
                "flight_time": ammo["flight_time"],
                "cost": ammo["cost"],
                "precision": ammo["precision"],
            },
            "t_flight": ammo["flight_time"],
            "sigma2": ammo["precision"],
        }
    return nodes


def _generate_dynamic_nodes(num_recon: int, num_command: int, num_fire: int, x_shift: float = 0.0, y_shift: float = 0.0):
    """按照数量自动生成节点，保持单目标不变。"""
    recon_list = []
    for i in range(num_recon):
        recon_list.append(
            {
                "coord": (-5.0 + (i % 5) + x_shift, 33.0 + (i // 5) + y_shift),
                "range": 5.5 + 0.1 * i,
                "sigma2": 1.0 + 0.05 * i,
                "t_deal": 5.0 + 0.1 * i,
                "parallel_limit": 1,
                "model": "侦察",
            }
        )

    command_list = []
    for i in range(num_command):
        command_list.append(
            {
                "coord": (-10.0 + (i % 3) + x_shift, 31.0 + (i // 3) + y_shift),
                "range": 5.5 + 0.12 * i,
                "t_deal": 3.5 + 0.05 * i,
                "command_capacity": 3,
            }
        )

    ammo_types = list(SAMPLE_AMMO.keys())
    fire_list = []
    for i in range(num_fire):
        ammo_type = ammo_types[i % len(ammo_types)]
        fire_list.append(
            {
                "coord": (-15.0 + (i % 5) + x_shift, 30.0 + (i // 5) + y_shift),
                "range": 14.0 + 0.4 * i,
                "t_deal": 8.0 + 0.15 * i,
                "ammo_type": ammo_type,
                "firepower_type": ammo_type,
            }
        )

    return _make_nodes(SAMPLE_TARGET_A["coord"], recon_list, command_list, fire_list)


def _build_presets():
    """返回内置的单目标方案，节点总数分别 10/20/30（含目标）。"""
    # 方案A：10节点 -> 1 目标 + 3 侦察 + 2 指挥 + 4 火力（基于论文样例裁剪）
    scheme_a = (
        "方案A-10节点",
        _make_nodes(SAMPLE_TARGET_A["coord"], SAMPLE_RECON_A[:3], SAMPLE_COMMAND_A, SAMPLE_FIRE_A[:4]),
    )
    # 方案B：20节点 -> 1 目标 + 8 侦察 + 5 指挥 + 6 火力
    scheme_b = (
        "方案B-20节点",
        _generate_dynamic_nodes(num_recon=8, num_command=5, num_fire=6, x_shift=0.6, y_shift=0.8),
    )
    # 方案C：30节点 -> 1 目标 + 12 侦察 + 8 指挥 + 9 火力
    scheme_c = (
        "方案C-30节点",
        _generate_dynamic_nodes(num_recon=12, num_command=8, num_fire=9, x_shift=-0.5, y_shift=-0.6),
    )
    return [scheme_a, scheme_b, scheme_c]


def _build_nodes_from_scheme(scheme_id: str, node_service: Optional[NodeService] = None, repo: Optional[MySQLRepository] = None):
    """从数据库加载指定方案的节点，构造成算法所需格式。"""
    repo = repo or MySQLRepository(DATABASE_CONFIG)
    node_service = node_service or NodeService(repo)
    raw = node_service.load_scheme_nodes(scheme_id)
    if not raw["targets"]:
        raise ValueError(f"方案 {scheme_id} 没有目标节点")

    nodes = {
        "target": raw["targets"][0]["coord"],
        "recon": {f"o{i+1}": n for i, n in enumerate(raw["recon"])},
        "command": {f"c{i+1}": n for i, n in enumerate(raw["command"])},
        "fire": {f"w{i+1}": n for i, n in enumerate(raw["fire"])},
    }
    return nodes


def _load_single_target_scenarios(limit: int = 3, preferred_names=None):
    """
    从数据库中挑选 target 节点数量为 1 的方案，作为默认对比用的单目标方案。
    优先使用数据库真实数据，便于复现 UI 中保存的方案；若查询失败，调用方负责回退。
    """
    preferred_names = preferred_names or ["论文方案"]
    repo = MySQLRepository(DATABASE_CONFIG)
    try:
        rows_main = list(repo.fetch_all(
            """
            SELECT s.scheme_id, s.scheme_name
            FROM scheme_master s
            JOIN (
                SELECT scheme_id, COUNT(*) AS target_cnt
                FROM target_nodes
                GROUP BY scheme_id
            ) t ON s.scheme_id = t.scheme_id
            WHERE t.target_cnt = 1
            ORDER BY s.scheme_name
            LIMIT %s
            """,
            (limit,),
        ))
        rows_preferred = []
        if preferred_names:
            placeholder = ", ".join(["%s"] * len(preferred_names))
            rows_preferred = list(repo.fetch_all(
                f"""
                SELECT s.scheme_id, s.scheme_name
                FROM scheme_master s
                JOIN (
                    SELECT scheme_id, COUNT(*) AS target_cnt
                    FROM target_nodes
                    GROUP BY scheme_id
                ) t ON s.scheme_id = t.scheme_id
                WHERE t.target_cnt = 1 AND s.scheme_name IN ({placeholder})
                """,
                tuple(preferred_names),
            ))
        rows = rows_main + [r for r in rows_preferred if r not in rows_main]
    except Exception as exc:
        print(f"[警告] 查询数据库单目标方案失败，将使用内置方案。原因: {exc}")
        return []
    if not rows:
        print("[提示] 数据库中未找到单目标方案，改用脚本内置方案。")
        return []

    node_service = NodeService(repo)
    scenarios = []
    for scheme_id, scheme_name in rows:
        try:
            scenarios.append((scheme_name, _build_nodes_from_scheme(scheme_id, node_service=node_service, repo=repo)))
        except Exception as exc:
            print(f"[警告] 方案 {scheme_name}({scheme_id}) 加载失败，跳过。原因: {exc}")
    return scenarios


def _build_all_nodes_list(nodes):
    """生成 loop_method/pso_method 所需的节点 key 顺序。"""
    return list(nodes["recon"].keys()) + list(nodes["command"].keys()) + list(nodes["fire"].keys()) + ["t1"]


def _extract_best_metrics(df: pd.DataFrame):
    """
    从评估表中提取核心指标的最佳值，容错处理空表或缺少列的情况。
    返回 NaN 以便后续绘图时保持行存在。
    """
    def _safe(stat_fn, col):
        if df is None or df.empty or col not in df.columns:
            return np.nan
        try:
            return stat_fn(df[col])
        except Exception:
            return np.nan

    return {
        "min_reaction": _safe(pd.Series.min, "反应时间(s)"),
        "min_precision": _safe(pd.Series.min, "打击精度(σ²)"),
        "max_firepower": _safe(pd.Series.max, "火力打击能力"),
        "max_match": _safe(pd.Series.max, "弹目匹配度"),
        "min_cost": _safe(pd.Series.min, "火力成本"),
    }


def _run_single_scenario(name: str, nodes: dict, runs: int = 1):
    """对单个方案运行两种算法并返回汇总指标。支持多次运行取均值/最优。"""
    all_nodes = _build_all_nodes_list(nodes)

    def _nan_reduce(values, reduce_fn):
        arr = np.array(values, dtype=float)
        if arr.size == 0 or np.all(np.isnan(arr)):
            return np.nan
        return reduce_fn(arr)

    def _run_algo(algo_name: str, fn):
        time_list, reaction_list, precision_list, firepower_list, match_list, cost_list, chains_list = [], [], [], [], [], [], []
        for i in range(runs):
            if algo_name == "粒子群":
                # 固定不同种子，保证多次运行可复现又不完全相同
                np.random.seed(i)
            t0 = time.perf_counter()
            res = fn(all_nodes, nodes)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            time_list.append(elapsed_ms)

            metrics = _extract_best_metrics(res["evaluation"])
            reaction = metrics["min_reaction"]
            precision = metrics["min_precision"]
            firepower = metrics["max_firepower"]
            match = metrics["max_match"]
            cost = metrics["min_cost"]
            chains = len(res["kill_chains"])

            reaction_list.append(reaction)
            precision_list.append(precision)
            firepower_list.append(firepower)
            match_list.append(match)
            cost_list.append(cost)
            chains_list.append(chains)

        return {
            "scenario": name,
            "algo": algo_name,
            "runs": runs,
            "time_ms": float(np.mean(time_list)),
            "min_reaction": _nan_reduce(reaction_list, np.nanmin),
            "min_precision": _nan_reduce(precision_list, np.nanmin),
            "max_firepower": _nan_reduce(firepower_list, np.nanmax),
            "max_match": _nan_reduce(match_list, np.nanmax),
            "min_cost": _nan_reduce(cost_list, np.nanmin),
            "chains": int(np.max(chains_list)) if chains_list else 0,
        }

    return [
        _run_algo("遍历", loop_method),
        _run_algo("粒子群", pso_method),
    ]


def _plot_results(df: pd.DataFrame, output_path: str):
    """生成多个方案的对比图。"""
    metrics = [
        ("time_ms", "耗时 (ms)"),
        ("min_reaction", "最佳反应时间"),
        ("min_precision", "最佳打击精度 ($\\sigma^2$)"),
        ("max_firepower", "最大火力打击能力"),
        ("max_match", "最大弹目匹配度"),
        ("min_cost", "最优火力成本"),
    ]
    n_metrics = len(metrics)
    n_cols = 3
    n_rows = int(np.ceil(n_metrics / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(14, 4 * n_rows))
    axes = axes.flatten()
    colors = {"遍历": "#4e79a7", "粒子群": "#f28e2b"}

    for ax, (col, title) in zip(axes, metrics):
        pivot = df.pivot(index="scenario", columns="algo", values=col)
        pivot.plot(kind="bar", ax=ax, color=[colors.get(a, "#666666") for a in pivot.columns])
        ax.set_title(title)
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        ax.set_xlabel("方案")
        legend = ax.get_legend()
        if legend:
            legend.set_title("")  # 去掉默认的列名“algo”
    # 隐藏多余子图
    for ax in axes[len(metrics):]:
        ax.axis("off")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"图像已保存到 {output_path}")


def main():
    parser = argparse.ArgumentParser(description="遍历 vs 粒子群 多方案对比")
    parser.add_argument("--scheme-ids", nargs="*", help="从数据库读取的 scheme_id 列表")
    parser.add_argument("--output", default="compare/algorithm_compare.png", help="输出图片路径")
    parser.add_argument("--runs", type=int, default=RUNS_DEFAULT, help=f"每种算法重复运行次数，用于取平均/最优指标（默认{RUNS_DEFAULT}次）")
    args = parser.parse_args()

    scenarios = []

    # 1) 指定 scheme_id：按用户请求加载
    if args.scheme_ids:
        for sid in args.scheme_ids:
            try:
                scenarios.append((f"scheme-{sid}", _build_nodes_from_scheme(sid)))
            except Exception as exc:
                print(f"[警告] 方案 {sid} 加载失败，原因: {exc}")

    # 2) 未指定时：拉取数据库中的单目标方案
    if not scenarios:
        scenarios = _load_single_target_scenarios()
        if not scenarios:
            print("[错误] 数据库中未找到单目标方案，或查询失败。请使用 --scheme-ids 指定方案。")
            return

    rows = []
    for name, nodes in scenarios:
        rows.extend(_run_single_scenario(name, nodes, runs=args.runs))

    df = pd.DataFrame(rows)

    # 控制台打印汇总
    for scenario in df["scenario"].unique():
        sub = df[df["scenario"] == scenario]
        loop_row = sub[sub["algo"] == "遍历"].iloc[0]
        pso_row = sub[sub["algo"] == "粒子群"].iloc[0]
        print(f"\n=== 方案 {scenario} ===")
        print(f"遍历: {loop_row['time_ms']:.1f} ms, 链数 {loop_row['chains']}, "
              f"反应 {loop_row['min_reaction']:.2f}, 精度 {loop_row['min_precision']:.2f}, 火力 {loop_row['max_firepower']:.2f}, "
              f"匹配度 {loop_row['max_match']:.2f}, 成本 {loop_row['min_cost']:.2f}")
        print(f"粒子群: {pso_row['time_ms']:.1f} ms, 链数 {pso_row['chains']}, "
              f"反应 {pso_row['min_reaction']:.2f}, 精度 {pso_row['min_precision']:.2f}, 火力 {pso_row['max_firepower']:.2f}, "
              f"匹配度 {pso_row['max_match']:.2f}, 成本 {pso_row['min_cost']:.2f}")

    _plot_results(df, args.output)


if __name__ == "__main__":
    main()
