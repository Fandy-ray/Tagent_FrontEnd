"""闪卡纯逻辑：去重、编号、公开投影、答案归一。全部离线，不碰 LLM。"""

import pytest
from pydantic import ValidationError

from app.schema.exam import cloze_matches, to_public
from app.util.text import deal_shards
from app.schema.flash import (
    FLASH_DEFAULT_TITLE,
    DraftFlashCard,
    DraftFlashChoice,
    FlashChoiceShardDraft,
    FlashClozeShardDraft,
    dedupe_cards,
    interleave,
    normalize_deck,
    normalized_accept,
    to_public_deck,
)


def card(text="甲 ____ 乙", accept=("答案",), match_mode="text", cue="提示"):
    return DraftFlashCard(cue=cue, text=text, accept=list(accept), match_mode=match_mode)


# ====================== 复用 exam.py 的校验器 ======================
def test_inherits_cloze_validators():
    with pytest.raises(ValidationError):
        card(text="没有空")            # 必须恰好一个 ____
    with pytest.raises(ValidationError):
        card(text="两个 ____ 和 ____")
    with pytest.raises(ValidationError):
        card(accept=[" ", ""])         # accept 不能全空白


def test_points_optional_on_draft():
    """闪卡的 prompt 去掉了分值那条规则，模型给不给 points 都不能报错。"""
    assert card().points is None
    assert DraftFlashCard(cue="c", text="甲 ____", accept=["a"], points=5).points == 5


# ====================== 去重 ======================
def test_dedupe_by_normalized_answer():
    kept = dedupe_cards([
        card(text="第一句 ____", accept=["服务机构", "服务机制"]),
        card(text="另一句 ____", accept=["服务机构。"]),   # 归一后同一个考点
        card(text="第三句 ____", accept=["排队规则"]),
    ])
    assert [c.accept[0] for c in kept] == ["服务机构", "排队规则"]


def test_dedupe_by_normalized_text():
    """答案写法不同但挖空句一样，仍是同一道题。"""
    kept = dedupe_cards([
        card(text="同一句 ____ 结尾", accept=["甲"]),
        card(text="同一句 ____ 结尾", accept=["乙"]),
    ])
    assert len(kept) == 1


def test_dedupe_keeps_first_and_order():
    kept = dedupe_cards([card(text=f"第 {i} 句 ____", accept=[f"答案{i}"]) for i in range(5)])
    assert [c.accept[0] for c in kept] == [f"答案{i}" for i in range(5)]


# ====================== 编号与分值 ======================
def test_normalize_deck_numbers_and_scores():
    deck = normalize_deck([card(text=f"句 {i} ____", accept=[f"a{i}"]) for i in range(3)],
                          "  ", "deck-1")
    assert [c.id for c in deck.cards] == ["F1", "F2", "F3"]
    assert {c.points for c in deck.cards} == {1}     # 闪卡不计分，恒为 1
    assert deck.title == FLASH_DEFAULT_TITLE          # 空白标题回落到默认


def test_normalize_deck_ignores_llm_ids():
    raw = card()
    raw.id = "LLM-GAVE-THIS"
    assert normalize_deck([raw], "标题", "deck-2").cards[0].id == "F1"


def test_empty_deck_rejected():
    with pytest.raises(ValidationError):
        normalize_deck([], "标题", "deck-3")


# ====================== 答案归一（与前端 cloze.ts 共享的用例表） ======================
# 改这张表时，同步 tagentnote/src/lib/data/cloze.ts 顶部的同名用例。
NORMALIZE_CASES = [
    # (用户输入, accept, match_mode, 是否应判对)
    ("服务机构", ["服务机构"], "text", True),
    ("  服务机构。 ", ["服务机构"], "text", True),      # 首尾空白 + 中文句号
    ("服务机构，", ["服务机构"], "text", True),
    ("ＭＷ", ["MW"], "text", True),                     # NFKC 全角→半角
    ("mw", ["MW"], "text", True),                       # text 模式不分大小写
    ("mW", ["MW"], "exact", False),                     # exact 模式大小写敏感
    ("MW", ["MW"], "exact", True),                      # 单位必须一模一样
    ("负 指数", ["负 指数"], "text", True),
    ("负  指数", ["负 指数"], "text", True),            # 空白折叠
    ("", ["答案"], "text", False),
    ("   ", ["答案"], "text", False),
    ("服务", ["服务机构"], "text", False),              # 只答上位概念不算对
]


@pytest.mark.parametrize("answer,accept,mode,expected", NORMALIZE_CASES)
def test_cloze_match_cases(answer, accept, mode, expected):
    assert cloze_matches(answer, accept, mode) is expected


@pytest.mark.parametrize("answer,accept,mode,expected", NORMALIZE_CASES)
def test_frontend_can_reproduce_with_accept_normalized(answer, accept, mode, expected):
    """前端只归一用户输入那一侧，参考侧直接用后端下发的 accept_normalized。

    这条用例就是在断言"那样做得出同样的结论"——两边一旦漂移，这里先炸。
    """
    from app.schema.exam import _normalize_exact_answer, _normalize_text_answer

    normalize = _normalize_exact_answer if mode == "exact" else _normalize_text_answer
    mine = normalize(answer)
    reference = normalized_accept(accept, mode)
    assert (bool(mine) and mine in reference) is expected


def test_normalized_accept_dedupes():
    assert normalized_accept(["服务机构", "服务机构。", "排队规则"], "text") == [
        "服务机构",
        "排队规则",
    ]


# ====================== 公开投影 ======================
def test_public_deck_carries_answers_on_purpose():
    deck = normalize_deck([card(accept=["服务机构", "服务机制"])], "标题", "deck-4")
    public = to_public_deck(deck)
    assert public.total_cards == 1
    only = public.cards[0]
    assert only.accept == ["服务机构", "服务机制"]
    assert only.accept_normalized == ["服务机构", "服务机制"]
    assert only.match_mode == "text"


def test_exam_public_projection_still_hides_answers():
    """闪卡下发答案是它自己那条路径的取舍，绝不能渗到整卷去。"""
    from tests.test_flash_service import make_full_exam

    public = to_public(make_full_exam())
    dumped = public.model_dump_json()
    for leaked in ("accept", "correct_index", "reference_answer", "rubric"):
        assert leaked not in dumped


def test_shard_draft_rejects_empty_list():
    with pytest.raises(ValidationError):
        FlashClozeShardDraft(cloze=[])
    with pytest.raises(ValidationError):
        FlashChoiceShardDraft(choice=[])


# ====================== 选择闪卡 ======================
def choice(question="λ/μ 叫什么？", correct=0, options=None):
    return DraftFlashChoice(
        question=question,
        options=options or ["服务强度", "到达率", "服务率", "队长"],
        correct_index=correct,
        explanation="说明",
    )


def test_choice_card_public_projection_carries_the_answer():
    deck = normalize_deck([choice()], "标题", "deck-c")
    only = to_public_deck(deck).cards[0]

    assert only.type == "choice"
    assert only.correct_index == 0
    assert only.options == ["服务强度", "到达率", "服务率", "队长"]


def test_dedupe_spans_both_card_types():
    """同一个考点出成填空还是选择都算重复——三片并发最容易撞出来的就是这个。"""
    kept = dedupe_cards([
        card(text="λ/μ 称为 ____", accept=["服务强度"]),
        choice(question="λ/μ 叫什么？", correct=0),   # 正确选项也是「服务强度」
        choice(question="仿真时钟怎么推进？", correct=1,
               options=["固定步长", "下次事件时间", "随机", "不推进"]),
    ])

    assert len(kept) == 2
    assert isinstance(kept[0], DraftFlashCard)
    assert isinstance(kept[1], DraftFlashChoice)


def test_mixed_deck_numbers_continuously():
    deck = normalize_deck([card(), choice(), card(text="另一句 ____", accept=["乙"])],
                          "标题", "deck-m")
    assert [c.id for c in deck.cards] == ["F1", "F2", "F3"]
    assert [c.type for c in deck.cards] == ["cloze", "choice", "cloze"]
    assert {c.points for c in deck.cards} == {1}


def test_interleave_spreads_choice_cards():
    cloze = [card(text=f"句 {i} ____", accept=[f"a{i}"]) for i in range(6)]
    picks = [choice(question=f"选 {i}") for i in range(2)]
    kinds = ["选择" if isinstance(c, DraftFlashChoice) else "填空"
             for c in interleave(cloze, picks)]

    assert kinds.count("选择") == 2
    # 不该前半段全填空、后半段全选择
    assert kinds.index("选择") < 4


def test_interleave_handles_empty_sides():
    only_cloze = [card()]
    assert interleave(only_cloze, []) == only_cloze
    picks = [choice()]
    assert interleave([], picks) == picks


# ====================== 材料分片（纯逻辑） ======================
SEP = "\n\n---\n\n"


def test_shards_get_disjoint_material():
    """各片材料互不相交——"分片不撞考点"这个说法全靠它。"""
    text = SEP.join(f"材料{i}" for i in range(9))
    shards = deal_shards(text, 3, separator=SEP, char_limit=1000)

    assert len(shards) == 3
    sets = [set(s.split(SEP)) for s in shards]
    for i in range(3):
        for j in range(i + 1, 3):
            assert sets[i] & sets[j] == set()
    assert set().union(*sets) == {f"材料{i}" for i in range(9)}


def test_one_oversized_piece_does_not_starve_the_rest_of_the_shard():
    """一份超大材料只该被跳过，不该把它后面还塞得下的一起挤掉。

    轮流发牌后 shard0 = [小, 巨, 小]。若遇到放不下就 break，第三份会连带丢失，
    那一片的材料量直接砍掉三分之一 —— 分片的全部意义就在材料的丰富度上。
    """
    pieces = ["小0", "x1", "x2", "巨" * 900, "y1", "y2", "小6", "z1", "z2"]
    shards = deal_shards(SEP.join(pieces), 3, separator=SEP, char_limit=200)

    assert shards[0].split(SEP) == ["小0", "小6"]


def test_first_piece_is_kept_even_when_over_limit():
    """宁可超出 char_limit，也不把一份材料截成半句话。"""
    huge = "长" * 500
    shards = deal_shards(huge, 1, separator=SEP, char_limit=100)
    assert shards == [huge]


def test_fewer_pieces_than_shards_never_yields_an_empty_shard():
    shards = deal_shards(SEP.join(["甲", "乙"]), 3, separator=SEP, char_limit=1000)
    assert shards == ["甲", "乙"]


def test_empty_material_yields_no_shards():
    assert deal_shards("", 3, separator=SEP, char_limit=1000) == []
    assert deal_shards(SEP + SEP, 3, separator=SEP, char_limit=1000) == []
