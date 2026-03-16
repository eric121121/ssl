"""算法服务，封装 UI 所需的算法入口。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from algorithms import (
    calculate_detailed_multi_target_metrics,
    enhanced_multi_target_ssl_allocation,
    generate_allocation_report,
    mopso_multi_target_allocation,
    pso_method,
    loop_method,
)


class AlgorithmService:
    """为 UI 提供统一的算法访问接口，避免界面层直接依赖具体算法模块。"""

    def run_loop(self, all_nodes, nodes):
        """单目标穷举搜索的代理方法。"""
        return loop_method(all_nodes, nodes)

    def run_pso(self, all_nodes, nodes):
        """单目标粒子群搜索的代理方法。"""
        return pso_method(all_nodes, nodes)

    def build_multi_target_ssl(self, targets, nodes, preference_table):
        """
        构建多目标杀伤链，考虑弹目偏好和多目标调度。

        参数：
            targets: dict 格式的目标集合
            nodes: 侦察/指挥/火力节点
            preference_table: 火力对目标的优先级矩阵
        """
        return enhanced_multi_target_ssl_allocation(targets, nodes, preference_table)

    def run_mopso_multi_target(
        self,
        targets,
        nodes,
        preference_table,
        *,
        num_particles: int,
        max_iterations: int,
        archive_size: int,
        random_seed: Optional[int] = None,
        use_hierarchical: bool = True,
    ) -> Dict[str, Any]:
        """
        运行多目标粒子群（MOPSO）算法。

        该方法只是一个轻量代理，负责把 UI 传来的可选参数拼装成命名参数传给底层算法。
        """
        return mopso_multi_target_allocation(
            targets,
            nodes,
            preference_table,
            num_particles=num_particles,
            max_iterations=max_iterations,
            archive_size=archive_size,
            random_seed=random_seed,
            use_hierarchical=use_hierarchical,
        )

    def generate_allocation_report(self, allocation, nodes, targets, all_chain_status=None):
        """封装报告生成，供 UI 复用同一套格式。"""
        return generate_allocation_report(allocation, nodes, targets, all_chain_status)

    def calculate_multi_target_metrics(self, allocation, nodes, targets, all_chain_status=None):
        """计算多目标指标（威胁覆盖、成本等）。"""
        return calculate_detailed_multi_target_metrics(allocation, nodes, targets, all_chain_status)
