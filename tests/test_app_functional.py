from __future__ import annotations

from pathlib import Path

import json
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROGRESS_FILE = ROOT / "data" / "progress.json"
WRONG_FILE = ROOT / "data" / "wrong_book.json"
EMPTY_PROGRESS = {"random": {"single": {}, "multiple": {}}, "sequential": {}, "exam": {}, "wrong_practice": {}}


@pytest.fixture(autouse=True)
def _reset_local_files():
    PROGRESS_FILE.write_text(json.dumps(EMPTY_PROGRESS, ensure_ascii=False, indent=2), encoding="utf-8")
    WRONG_FILE.write_text("{}", encoding="utf-8")
    yield
    PROGRESS_FILE.write_text(json.dumps(EMPTY_PROGRESS, ensure_ascii=False, indent=2), encoding="utf-8")
    WRONG_FILE.write_text("{}", encoding="utf-8")

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _run() -> AppTest:
    return AppTest.from_file(APP, default_timeout=15).run()


def _set_page(at: AppTest, page: str) -> AppTest:
    for radio in at.radio:
        if radio.label == "选择板块":
            radio.set_value(page)
            return at.run()
    raise AssertionError("找不到侧边栏板块选择控件")


def _click(at: AppTest, label: str) -> AppTest:
    for button in at.button:
        if button.label == label:
            button.click()
            return at.run()
    raise AssertionError(f"找不到按钮：{label}")


def _choose_first_single(at: AppTest) -> AppTest:
    for radio in at.radio:
        if radio.label == "请选择一个答案：":
            radio.set_value(radio.options[0])
            return at
    raise AssertionError("找不到单选答题控件")


def _choose_first_multiple(at: AppTest) -> AppTest:
    # 多选题现在使用逐项 checkbox，不再使用 multiselect 下拉框。
    for cb in at.checkbox:
        if cb.label.startswith("A. "):
            cb.set_value(True)
            return at
    raise AssertionError("找不到多选 checkbox 答题控件")


def test_random_single_can_submit_and_next() -> None:
    at = _run()
    at = _choose_first_single(at)
    at = _click(at, "提交答案")
    assert not at.exception
    assert any(x.value in {"回答正确！", "回答错误。已加入错题本。"} for x in [*at.success, *at.error])
    at = _click(at, "下一题")
    assert not at.exception
    assert "当前进度：2 /" in "\n".join(x.value for x in at.caption)


def test_random_multiple_can_submit_and_next() -> None:
    at = _set_page(_run(), "随机多选题")
    at = _choose_first_multiple(at)
    at = _click(at, "提交答案")
    assert not at.exception
    assert any(x.value in {"回答正确！", "回答错误。已加入错题本。"} for x in [*at.success, *at.error])
    at = _click(at, "下一题")
    assert not at.exception
    assert "当前进度：2 /" in "\n".join(x.value for x in at.caption)


def test_sequential_can_submit_and_next() -> None:
    at = _set_page(_run(), "顺序刷题")
    at = _choose_first_single(at)
    at = _click(at, "提交答案")
    assert not at.exception
    assert any(x.value in {"回答正确！", "回答错误。已加入错题本。"} for x in [*at.success, *at.error])
    at = _click(at, "下一题")
    assert not at.exception
    assert "当前进度：2 /" in "\n".join(x.value for x in at.caption)


def test_exam_is_single_question_page_with_nav_and_guarded_submit() -> None:
    at = _set_page(_run(), "模拟考试")
    all_text = "\n".join([*(x.value for x in at.markdown), *(x.value for x in at.caption)])
    assert "第一部分 单项选择题" in all_text
    assert "第二部分 多项选择题" in all_text
    assert "题号导航" in all_text
    assert len(at.session_state["exam_order"]) == 100
    first_70 = at.session_state["exam_order"][:70]
    last_30 = at.session_state["exam_order"][70:]
    assert all(k.startswith("single:") for k in first_70)
    assert all(k.startswith("multiple:") for k in last_30)

    # 跳到最后一题但不填完所有题，应该禁止交卷。
    at.session_state["exam_current_index"] = 99
    at = at.run()
    at = _click(at, "提交试卷")
    assert not at.exception
    assert any("不能提交试卷" in x.value for x in at.warning)

    # 填充所有答案后，可以交卷并显示结果。
    qmap = at.session_state["qmap"]
    at.session_state["exam_answers"] = {key: qmap[key]["answer"] for key in at.session_state["exam_order"]}
    at.session_state["exam_current_index"] = 99
    at = at.run()
    at = _click(at, "提交试卷")
    assert not at.exception
    assert any(m.label == "总分" for m in at.metric)


def test_wrong_book_page_loads() -> None:
    at = _set_page(_run(), "错题本")
    assert not at.exception
    assert any(x.value == "错题本" for x in at.subheader)


def test_random_single_progress_is_saved_to_local_file() -> None:
    at = _run()
    at = _choose_first_single(at)
    at = _click(at, "提交答案")
    at = _click(at, "下一题")
    progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    assert progress["random"]["single"]["current_index"] == 1
    assert progress["random"]["single"]["order"]


def test_sequential_progress_is_saved_to_local_file() -> None:
    at = _set_page(_run(), "顺序刷题")
    at = _choose_first_single(at)
    at = _click(at, "提交答案")
    at = _click(at, "下一题")
    progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    assert progress["sequential"]["current_index"] == 1
    assert progress["sequential"]["order"][0] == "single:1"


def test_exam_progress_is_saved_to_local_file() -> None:
    at = _set_page(_run(), "模拟考试")
    assert not at.exception
    progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    assert len(progress["exam"]["order"]) == 100
    assert all(k.startswith("single:") for k in progress["exam"]["order"][:70])
    assert all(k.startswith("multiple:") for k in progress["exam"]["order"][70:])


def _sample_wrong_book() -> dict:
    questions = json.loads((ROOT / "data" / "questions.json").read_text(encoding="utf-8"))
    q1 = next(q for q in questions if q["type"] == "single" and q["id"] == 1)
    q2 = next(q for q in questions if q["type"] == "single" and q["id"] == 2)
    return {
        "single:1": {
            **q1,
            "wrong_count": 1,
            "wrong_choices": ["A"],
            "last_wrong_at": "2026-01-01 00:00:00",
        },
        "single:2": {
            **q2,
            "wrong_count": 2,
            "wrong_choices": ["A"],
            "last_wrong_at": "2026-01-01 00:00:00",
        },
    }


def test_wrong_book_practice_hides_answer_before_submit_and_can_next() -> None:
    WRONG_FILE.write_text(json.dumps(_sample_wrong_book(), ensure_ascii=False, indent=2), encoding="utf-8")
    at = _set_page(_run(), "错题本")
    assert not at.exception
    all_markdown_before = "\n".join(x.value for x in at.markdown)
    assert "正确答案" not in all_markdown_before
    at = _choose_first_single(at)
    at = _click(at, "提交答案")
    assert not at.exception
    all_markdown_after = "\n".join(x.value for x in at.markdown)
    assert "正确答案" in all_markdown_after
    at = _click(at, "下一题")
    assert not at.exception
    assert "当前进度：2 /" in "\n".join(x.value for x in at.caption)
