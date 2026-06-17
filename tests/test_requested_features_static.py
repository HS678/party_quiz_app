from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_TEXT = (ROOT / "app.py").read_text(encoding="utf-8")


def test_multiple_choice_uses_checkboxes_not_multiselect():
    assert "st.checkbox" in APP_TEXT
    assert "st.multiselect" not in APP_TEXT


def test_exam_is_one_question_with_navigation_and_submit_guard():
    assert "render_exam_one_question" in APP_TEXT
    assert "render_exam_navigation" in APP_TEXT
    assert "还有 {len(unanswered)} 道题未作答，不能提交试卷" in APP_TEXT
    assert "submit_exam_if_complete" in APP_TEXT


def test_exam_has_wrong_recap_and_wrong_redo():
    assert "本次错题回顾" in APP_TEXT
    assert "本次错题重做" in APP_TEXT
    assert "考试时你的答案" in APP_TEXT


def test_practice_pages_have_submit_previous_next_buttons():
    assert APP_TEXT.count('"提交答案"') >= 3
    assert APP_TEXT.count('"上一题"') >= 4
    assert APP_TEXT.count('"下一题"') >= 4



def test_all_practice_pages_have_right_side_navigation_helpers():
    assert "render_random_navigation" in APP_TEXT
    assert "render_sequential_navigation" in APP_TEXT
    assert "render_wrong_navigation" in APP_TEXT
    assert "render_exam_wrong_review_navigation" in APP_TEXT
    assert APP_TEXT.count("题号索引") >= 3
    assert "点击题号可以跳转到对应题目" in APP_TEXT


def test_wrong_and_sequential_multiple_choice_share_checkbox_selector():
    assert "render_answer_selector(" in APP_TEXT
    assert "多选使用逐项 checkbox" in APP_TEXT
    assert "key_prefix=f\"seq_{q['type']}_{q['id']}_{idx}\"" in APP_TEXT
    assert "key_prefix=f\"wrong_{item['type']}_{item['id']}_{idx}\"" in APP_TEXT
