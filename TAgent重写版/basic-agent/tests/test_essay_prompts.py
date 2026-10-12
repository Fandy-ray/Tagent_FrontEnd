"""定量批改的提示契约和校验例；不把提示词检查当作真实模型判定测试。"""

from fractions import Fraction
import re

import pytest

from app.prompts.essay_prompts import (
    QUANTITATIVE_REVIEW_RULES,
    build_annotation_prompt,
    build_dimension_prompt,
)


@pytest.mark.parametrize("service_rate", [10, 12])
def test_mm1_reference_examples_match_independent_stationary_calculation(service_rate):
    """从提示中提取真实示例数值，用稳态几何分布均值和 Little 关系独立复算。"""
    example = re.search(
        rf"λ=6 人/小时、μ={service_rate} 人/小时："
        r"Wq=([\d./]+) 小时=([\d./]+) 分钟，Lq=([\d./]+) 人；\s*"
        r"W=([\d./]+) 小时=([\d./]+) 分钟，L=([\d./]+) 人。",
        QUANTITATIVE_REVIEW_RULES,
    )
    assert example is not None, "两组参数的队列/系统指标校验例都必须保留"
    arrival_rate = Fraction(6)
    utilization = arrival_rate / service_rate
    system_population = utilization / (1 - utilization)
    queue_population = system_population - utilization
    system_hours = system_population / arrival_rate
    queue_hours = queue_population / arrival_rate

    assert tuple(map(Fraction, example.groups())) == (
        queue_hours, queue_hours * 60, queue_population,
        system_hours, system_hours * 60, system_population,
    )
    assert system_hours - queue_hours == Fraction(1, service_rate)
    if service_rate == 10:
        assert (queue_hours * 60, queue_population) == (9, Fraction("0.9"))
        assert (system_hours * 60, system_population) == (15, Fraction("1.5"))


def test_ambiguity_requests_clarification_without_asserting_a_numerical_error():
    text = "P2S1 平均等待时间为9分钟，平均人数为0.9人。"
    prompt = build_annotation_prompt(text)
    assert "用 suggestion 提出具体澄清问题" in prompt
    assert "不能用 issue 判数值错误" in prompt
    assert "是否含服务时间或服务中人数" in prompt
    assert "缺少推导展示不等于数值错误" in prompt
    assert "也不能据此认定有关计算准确性的评分要点未命中" in prompt
    assert prompt.rsplit("句子：\n", 1)[1] == text

    argument = build_dimension_prompt("argument", text, want_flags=True)
    assert "需澄清指标含义的段落也可列入，这不等于判定数值错误" in argument


def test_formulas_require_matching_model_definitions_and_units():
    rules = QUANTITATIVE_REVIEW_RULES
    for boundary in (
        "0 < λ < μ", "无容量限制", "无顾客放弃",
        "其他排队模型、有容量限制、非稳态或有限样本的仿真统计",
        "不得直接套用上述稳态 M/M/1 公式", "λ >= μ",
        "不能将人/小时直接乘分钟", "根据该定义选择适用公式",
        "含义优先于符号", "指标含义、公式、代入/单位换算及正确结果",
    ):
        assert boundary in rules
    assert "Wq：排队等待时间，不含接受服务的时间" in rules
    assert "Lq：队列人数，不含正在接受服务的人" in rules
    assert "W：系统逗留时间，包含排队与服务时间" in rules
    assert "L：系统人数，包含排队与正在服务的人" in rules
