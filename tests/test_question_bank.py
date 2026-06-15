import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = json.loads((ROOT / "data" / "questions.json").read_text(encoding="utf-8"))


def test_question_counts():
    assert sum(q["type"] == "single" for q in QUESTIONS) == 306
    assert sum(q["type"] == "multiple" for q in QUESTIONS) == 78
    assert len(QUESTIONS) == 384


def test_ids_are_continuous_inside_each_section():
    for typ in ["single", "multiple"]:
        ids = [q["id"] for q in QUESTIONS if q["type"] == typ]
        assert ids == list(range(1, max(ids) + 1))


def test_answer_letters_match_existing_options():
    for q in QUESTIONS:
        assert q["answer"], q
        assert set(q["answer"]).issubset(set(q["options"].keys())), q
        if q["type"] == "single":
            assert len(q["answer"]) == 1, q
            assert len(q["options"]) == 3, q
        else:
            assert len(q["answer"]) >= 2, q
            assert len(q["options"]) == 4, q


def test_representative_answers_from_source():
    q1 = next(q for q in QUESTIONS if q["type"] == "single" and q["id"] == 1)
    assert q1["answer"] == ["B"]
    assert q1["options"]["B"] == "2022年10月22日"
    q306 = next(q for q in QUESTIONS if q["type"] == "single" and q["id"] == 306)
    assert q306["answer"] == ["C"]
    mq1 = next(q for q in QUESTIONS if q["type"] == "multiple" and q["id"] == 1)
    assert mq1["answer"] == ["A", "C"]
    mq78 = next(q for q in QUESTIONS if q["type"] == "multiple" and q["id"] == 78)
    assert mq78["answer"] == ["A", "B", "C"]


def test_exam_question_bank_is_sufficient():
    singles = [q for q in QUESTIONS if q["type"] == "single"]
    multiples = [q for q in QUESTIONS if q["type"] == "multiple"]
    assert len(singles) >= 70
    assert len(multiples) >= 30


def test_sequential_order_is_single_then_multiple():
    singles = sorted([q for q in QUESTIONS if q["type"] == "single"], key=lambda x: x["id"])
    multiples = sorted([q for q in QUESTIONS if q["type"] == "multiple"], key=lambda x: x["id"])
    order = [(q["type"], q["id"]) for q in singles + multiples]
    assert order[0] == ("single", 1)
    assert order[305] == ("single", 306)
    assert order[306] == ("multiple", 1)
    assert order[-1] == ("multiple", 78)


def test_exam_order_requirement_single_first_multiple_second():
    singles = [q for q in QUESTIONS if q["type"] == "single"][:70]
    multiples = [q for q in QUESTIONS if q["type"] == "multiple"][:30]
    order = singles + multiples
    assert len(order) == 100
    assert all(q["type"] == "single" for q in order[:70])
    assert all(q["type"] == "multiple" for q in order[70:])


def test_app_contains_exam_section_titles():
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "第一部分 单项选择题" in app_text
    assert "第二部分 多项选择题" in app_text
    assert "selected_singles + selected_multiples" in app_text
