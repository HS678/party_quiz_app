from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "questions.json"
WRONG_FILE = ROOT / "data" / "wrong_book.json"
PROGRESS_FILE = ROOT / "data" / "progress.json"

EXAM_SINGLE_COUNT = 70
EXAM_MULTIPLE_COUNT = 30
EXAM_TOTAL_COUNT = EXAM_SINGLE_COUNT + EXAM_MULTIPLE_COUNT


# ========== 基础数据读写 ==========

def load_questions() -> list[dict[str, Any]]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def load_wrong_book() -> dict[str, Any]:
    if not WRONG_FILE.exists():
        return {}
    try:
        data = json.loads(WRONG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_wrong_book(book: dict[str, Any]) -> None:
    WRONG_FILE.write_text(json.dumps(book, ensure_ascii=False, indent=2), encoding="utf-8")


def default_progress() -> dict[str, Any]:
    return {
        "random": {
            "single": {},
            "multiple": {},
        },
        "sequential": {},
        "exam": {},
        "wrong_practice": {},
    }


def load_progress() -> dict[str, Any]:
    if not PROGRESS_FILE.exists():
        return default_progress()
    try:
        data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_progress()
    if not isinstance(data, dict):
        return default_progress()

    # 兼容旧版本/空文件，保证必要字段存在。
    base = default_progress()
    if isinstance(data.get("random"), dict):
        base["random"].update(data["random"])
    if isinstance(data.get("sequential"), dict):
        base["sequential"].update(data["sequential"])
    if isinstance(data.get("exam"), dict):
        base["exam"].update(data["exam"])
    if isinstance(data.get("wrong_practice"), dict):
        base["wrong_practice"].update(data["wrong_practice"])
    return base


def save_progress(progress: dict[str, Any]) -> None:
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_progress() -> None:
    save_progress(default_progress())


def qkey(q: dict[str, Any]) -> str:
    return f"{q['type']}:{q['id']}"


def type_name(qtype: str) -> str:
    return "单选" if qtype == "single" else "多选"


def check_answer(choice: list[str], answer: list[str]) -> bool:
    return sorted(choice) == sorted(answer)


def record_wrong(q: dict[str, Any], choice: list[str]) -> None:
    book = load_wrong_book()
    key = qkey(q)
    item = book.get(key, {
        "wrong_count": 0,
        "wrong_choices": [],
        "last_wrong_at": "",
    })
    # 每次记录错题时都同步当前题库中的题干、答案和解析，避免旧版本 wrong_book.json
    # 保留过时的解析文本。
    item["id"] = q["id"]
    item["type"] = q["type"]
    item["question"] = q["question"]
    item["options"] = q["options"]
    item["answer"] = q["answer"]
    item["explanation"] = q["explanation"]
    item["wrong_count"] = int(item.get("wrong_count", 0)) + 1
    item.setdefault("wrong_choices", [])
    item["last_wrong_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    choice_text = "".join(sorted(choice)) if choice else "未选择"
    if choice_text not in item["wrong_choices"]:
        item["wrong_choices"].append(choice_text)
    book[key] = item
    save_wrong_book(book)


def sync_wrong_book_with_questions(book: dict[str, Any], qmap: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """把旧版本错题本记录同步到当前题库格式。"""
    changed = False
    synced: dict[str, Any] = {}
    for key, item in book.items():
        q = qmap.get(key)
        if not q:
            changed = True
            continue
        new_item = dict(item) if isinstance(item, dict) else {}
        for field in ["id", "type", "question", "options", "answer", "explanation"]:
            if new_item.get(field) != q.get(field):
                new_item[field] = q.get(field)
                changed = True
        try:
            new_item["wrong_count"] = int(new_item.get("wrong_count", 0))
        except (TypeError, ValueError):
            new_item["wrong_count"] = 0
            changed = True
        if not isinstance(new_item.get("wrong_choices"), list):
            new_item["wrong_choices"] = []
            changed = True
        new_item.setdefault("last_wrong_at", "")
        synced[key] = new_item
    if changed or len(synced) != len(book):
        save_wrong_book(synced)
    return synced


def format_options(q: dict[str, Any], letters: list[str]) -> str:
    if not letters:
        return "未选择"
    return "；".join(f"{x}. {q['options'].get(x, '')}" for x in sorted(letters))


def option_label_map(q: dict[str, Any]) -> tuple[list[str], dict[str, str], dict[str, str]]:
    labels = [f"{k}. {v}" for k, v in q["options"].items()]
    label_to_key = {f"{k}. {v}": k for k, v in q["options"].items()}
    key_to_label = {k: f"{k}. {v}" for k, v in q["options"].items()}
    return labels, label_to_key, key_to_label


def valid_order(order: Any) -> bool:
    return isinstance(order, list) and bool(order) and all(k in st.session_state.qmap for k in order)


def wrong_qkey(item: dict[str, Any]) -> str:
    return f"{item['type']}:{item['id']}"


def valid_wrong_order(order: Any, book: dict[str, Any]) -> bool:
    return isinstance(order, list) and bool(order) and all(k in book for k in order)


def clamp_index(value: Any, total: int) -> int:
    try:
        idx = int(value)
    except (TypeError, ValueError):
        idx = 0
    if total <= 0:
        return 0
    return max(0, min(idx, total - 1))


def render_answer_selector(
    q: dict[str, Any],
    key_prefix: str,
    stored_choice: list[str] | None = None,
    disabled: bool = False,
) -> list[str]:
    """统一答题控件。

    单选使用 radio；多选使用逐项 checkbox，不再使用 multiselect 下拉框，避免选项不易点中的问题。
    """
    stored = [x for x in (stored_choice or []) if x in q["options"]]
    labels, label_to_key, key_to_label = option_label_map(q)

    if q["type"] == "single":
        default_index = None
        if stored:
            stored_label = key_to_label.get(stored[0])
            if stored_label in labels:
                default_index = labels.index(stored_label)
        selected = st.radio(
            "请选择一个答案：",
            labels,
            index=default_index,
            key=f"{key_prefix}_radio",
            disabled=disabled,
        )
        return [label_to_key[selected]] if selected else []

    st.markdown("请选择一个或多个答案：")
    choice: list[str] = []
    for letter, text in q["options"].items():
        checked = st.checkbox(
            f"{letter}. {text}",
            value=letter in stored,
            key=f"{key_prefix}_check_{letter}",
            disabled=disabled,
        )
        if checked:
            choice.append(letter)
    return choice


def render_explanation(explanation: str) -> None:
    """以更适合阅读的方式展示 Markdown 题目解析。"""
    with st.container(border=True):
        st.markdown(explanation)


def show_answer_result(q: dict[str, Any], user_choice: list[str], wrong_text: str = "回答错误。已加入错题本。") -> None:
    ok = check_answer(user_choice, q["answer"])
    if ok:
        st.success("回答正确！")
    else:
        st.error(wrong_text)
    st.markdown(f"**你的答案：** {format_options(q, user_choice)}")
    st.markdown(f"**正确答案：** {format_options(q, q['answer'])}")
    render_explanation(q["explanation"])


# ========== 右侧题号索引 ===========

def render_question_index_grid(
    title: str,
    indices: list[int],
    current_index: int,
    key_prefix: str,
    label_func,
    on_jump,
    cols_count: int = 5,
) -> None:
    """渲染可点击题号索引。indices 为 0-based 题目位置。"""
    st.markdown(f"#### {title}")
    st.caption("点击题号可以跳转到对应题目。")
    for row_start in range(0, len(indices), cols_count):
        row = indices[row_start: row_start + cols_count]
        cols = st.columns(cols_count)
        for j, index in enumerate(row):
            with cols[j]:
                if st.button(
                    str(label_func(index)),
                    key=f"{key_prefix}_{index}",
                    type="primary" if index == current_index else "secondary",
                    use_container_width=True,
                ):
                    on_jump(index)
                    st.rerun()


def render_random_navigation(qtype: str) -> None:
    total = len(st.session_state.random_order)

    def jump(index: int) -> None:
        st.session_state.random_current_index = index
        st.session_state.random_submitted = False
        st.session_state.random_last_choice = []
        save_random_progress()

    st.caption("索引为本轮随机顺序，不是原文题号。")
    render_question_index_grid(
        "题号索引",
        list(range(total)),
        st.session_state.random_current_index,
        f"random_nav_{qtype}",
        lambda i: i + 1,
        jump,
        cols_count=5,
    )


def render_sequential_navigation() -> None:
    order = st.session_state.seq_order
    single_indices = [i for i, key in enumerate(order) if st.session_state.qmap[key]["type"] == "single"]
    multiple_indices = [i for i, key in enumerate(order) if st.session_state.qmap[key]["type"] == "multiple"]

    def jump(index: int) -> None:
        st.session_state.seq_current_index = index
        st.session_state.seq_submitted = False
        st.session_state.seq_last_choice = []
        save_sequential_progress()

    st.markdown("#### 题号索引")
    st.caption("单选按原文 1—306，多选按原文 1—78。")
    with st.expander("单选题 1—306", expanded=False):
        render_question_index_grid(
            "单选题号",
            single_indices,
            st.session_state.seq_current_index,
            "seq_nav_single",
            lambda i: st.session_state.qmap[order[i]]["id"],
            jump,
            cols_count=5,
        )
    with st.expander("多选题 1—78", expanded=False):
        render_question_index_grid(
            "多选题号",
            multiple_indices,
            st.session_state.seq_current_index,
            "seq_nav_multiple",
            lambda i: st.session_state.qmap[order[i]]["id"],
            jump,
            cols_count=5,
        )


def render_wrong_navigation(book: dict[str, Any]) -> None:
    total = len(st.session_state.wrong_order)

    def jump(index: int) -> None:
        st.session_state.wrong_current_index = index
        st.session_state.wrong_submitted = False
        st.session_state.wrong_last_choice = []
        save_wrong_practice_progress()

    def label(index: int) -> str:
        item = book[st.session_state.wrong_order[index]]
        return f"{index + 1}"

    st.caption("索引为本轮错题练习顺序。")
    render_question_index_grid(
        "错题索引",
        list(range(total)),
        st.session_state.wrong_current_index,
        "wrong_nav",
        label,
        jump,
        cols_count=5,
    )


def render_exam_wrong_review_navigation(wrong_keys: list[str]) -> None:
    def jump(index: int) -> None:
        st.session_state.exam_wrong_review_index = index
        st.session_state.exam_wrong_review_submitted = False
        st.session_state.exam_wrong_review_last_choice = []
        save_exam_progress()

    render_question_index_grid(
        "错题索引",
        list(range(len(wrong_keys))),
        st.session_state.exam_wrong_review_index,
        "exam_wrong_review_nav",
        lambda i: i + 1,
        jump,
        cols_count=5,
    )


# ========== 进度持久化 ==========

def save_random_progress() -> None:
    qtype = st.session_state.random_practice_type
    if qtype not in {"single", "multiple"}:
        return
    st.session_state.progress["random"][qtype] = {
        "order": st.session_state.random_order,
        "current_index": st.session_state.random_current_index,
        "submitted": st.session_state.random_submitted,
        "last_choice": st.session_state.random_last_choice,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_progress(st.session_state.progress)


def save_sequential_progress() -> None:
    st.session_state.progress["sequential"] = {
        "order": st.session_state.seq_order,
        "current_index": st.session_state.seq_current_index,
        "submitted": st.session_state.seq_submitted,
        "last_choice": st.session_state.seq_last_choice,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_progress(st.session_state.progress)


def save_exam_progress() -> None:
    st.session_state.progress["exam"] = {
        "order": st.session_state.exam_order,
        "current_index": st.session_state.exam_current_index,
        "submitted": st.session_state.exam_submitted,
        "recorded_wrong": st.session_state.exam_recorded_wrong,
        "answers": st.session_state.exam_answers,
        "wrong_review_index": st.session_state.exam_wrong_review_index,
        "wrong_review_submitted": st.session_state.exam_wrong_review_submitted,
        "wrong_review_last_choice": st.session_state.exam_wrong_review_last_choice,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_progress(st.session_state.progress)


def save_wrong_practice_progress() -> None:
    st.session_state.progress["wrong_practice"] = {
        "order": st.session_state.wrong_order,
        "current_index": st.session_state.wrong_current_index,
        "submitted": st.session_state.wrong_submitted,
        "last_choice": st.session_state.wrong_last_choice,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_progress(st.session_state.progress)


# ========== 随机练习 ==========

def reset_random_practice(qtype: str) -> None:
    questions = [q for q in st.session_state.questions if q["type"] == qtype]
    random.shuffle(questions)
    st.session_state.random_practice_type = qtype
    st.session_state.random_order = [qkey(q) for q in questions]
    st.session_state.random_current_index = 0
    st.session_state.random_submitted = False
    st.session_state.random_last_choice = []
    save_random_progress()


def restore_random_practice(qtype: str) -> None:
    progress = st.session_state.progress.get("random", {}).get(qtype, {})
    order = progress.get("order")
    if valid_order(order):
        st.session_state.random_practice_type = qtype
        st.session_state.random_order = order
        st.session_state.random_current_index = clamp_index(progress.get("current_index", 0), len(order))
        st.session_state.random_submitted = bool(progress.get("submitted", False))
        st.session_state.random_last_choice = list(progress.get("last_choice", []))
    else:
        reset_random_practice(qtype)


def get_random_current_question() -> dict[str, Any] | None:
    if not st.session_state.get("random_order"):
        return None
    key = st.session_state.random_order[st.session_state.random_current_index]
    return st.session_state.qmap[key]


def render_random_practice(qtype: str) -> None:
    title = "随机单选题" if qtype == "single" else "随机多选题"
    if st.session_state.get("random_practice_type") != qtype or not st.session_state.get("random_order"):
        restore_random_practice(qtype)

    total = len(st.session_state.random_order)
    idx = st.session_state.random_current_index

    title_col, reset_col = st.columns([3, 1])
    with title_col:
        st.subheader(title)
    with reset_col:
        if st.button("重新随机本版块", key=f"random_top_reset_{qtype}"):
            reset_random_practice(qtype)
            st.rerun()

    if total == 0:
        st.warning("该板块暂无题目。")
        return
    if idx >= total:
        st.success("本板块题目已经全部练习完毕。")
        if st.button("重新练习", type="primary"):
            reset_random_practice(qtype)
            st.rerun()
        return

    q = get_random_current_question()
    if q is None:
        st.warning("该板块暂无题目。")
        return

    main_col, nav_col = st.columns([4, 1], gap="large")
    with main_col:
        st.progress((idx + 1) / total)
        st.caption(f"当前进度：{idx + 1} / {total}，原文题号：第 {q['id']} 题")
        st.markdown(f"### 第 {q['id']} 题")
        st.write(q["question"])

        choice = render_answer_selector(
            q,
            key_prefix=f"random_{qtype}_{q['id']}_{idx}",
            stored_choice=st.session_state.random_last_choice if st.session_state.random_submitted else [],
            disabled=st.session_state.random_submitted,
        )

        c_submit, c_prev, c_next = st.columns([1, 1, 1])
        with c_submit:
            submit = st.button(
                "提交答案",
                type="primary",
                key=f"random_submit_{qtype}_{q['id']}_{idx}",
                disabled=st.session_state.random_submitted,
            )
        with c_prev:
            prev_clicked = st.button(
                "上一题",
                key=f"random_prev_{qtype}_{q['id']}_{idx}",
                disabled=idx == 0,
            )
        with c_next:
            next_clicked = st.button(
                "下一题",
                key=f"random_next_{qtype}_{q['id']}_{idx}",
                disabled=not st.session_state.random_submitted,
            )

        if submit:
            if not choice:
                st.warning("请先选择答案。")
                return
            st.session_state.random_submitted = True
            st.session_state.random_last_choice = choice
            if not check_answer(choice, q["answer"]):
                record_wrong(q, choice)
            save_random_progress()
            st.rerun()

        if prev_clicked:
            st.session_state.random_current_index = max(0, idx - 1)
            st.session_state.random_submitted = False
            st.session_state.random_last_choice = []
            save_random_progress()
            st.rerun()

        if next_clicked:
            st.session_state.random_current_index += 1
            st.session_state.random_submitted = False
            st.session_state.random_last_choice = []
            save_random_progress()
            st.rerun()

        if st.session_state.random_submitted:
            show_answer_result(q, st.session_state.random_last_choice)

    with nav_col:
        render_random_navigation(qtype)


# ========== 顺序刷题 ==========

def reset_sequential_practice() -> None:
    singles = sorted([q for q in st.session_state.questions if q["type"] == "single"], key=lambda x: x["id"])
    multiples = sorted([q for q in st.session_state.questions if q["type"] == "multiple"], key=lambda x: x["id"])
    st.session_state.seq_order = [qkey(q) for q in singles + multiples]
    st.session_state.seq_current_index = 0
    st.session_state.seq_submitted = False
    st.session_state.seq_last_choice = []
    save_sequential_progress()


def restore_sequential_practice() -> None:
    progress = st.session_state.progress.get("sequential", {})
    order = progress.get("order")
    if valid_order(order):
        st.session_state.seq_order = order
        st.session_state.seq_current_index = clamp_index(progress.get("current_index", 0), len(order))
        st.session_state.seq_submitted = bool(progress.get("submitted", False))
        st.session_state.seq_last_choice = list(progress.get("last_choice", []))
    else:
        reset_sequential_practice()


def render_sequential_practice() -> None:
    if not st.session_state.get("seq_order"):
        restore_sequential_practice()

    total = len(st.session_state.seq_order)
    idx = st.session_state.seq_current_index
    title_col, reset_col = st.columns([3, 1])
    with title_col:
        st.subheader("顺序刷题")
    with reset_col:
        if st.button("重新开始顺序刷题", key="seq_top_reset"):
            reset_sequential_practice()
            st.rerun()
    st.caption("按照原文题号顺序练习：先刷完全部单选题，再刷多选题。")

    if idx >= total:
        st.success("全部题目已经顺序练习完毕。")
        if st.button("重新开始顺序刷题", type="primary"):
            reset_sequential_practice()
            st.rerun()
        return

    q = st.session_state.qmap[st.session_state.seq_order[idx]]
    main_col, nav_col = st.columns([4, 1], gap="large")
    with main_col:
        st.progress((idx + 1) / total)
        st.caption(f"当前进度：{idx + 1} / {total}｜{type_name(q['type'])}｜原文第 {q['id']} 题")
        st.markdown(f"### [{type_name(q['type'])}] 第 {q['id']} 题")
        st.write(q["question"])

        choice = render_answer_selector(
            q,
            key_prefix=f"seq_{q['type']}_{q['id']}_{idx}",
            stored_choice=st.session_state.seq_last_choice if st.session_state.seq_submitted else [],
            disabled=st.session_state.seq_submitted,
        )

        c_submit, c_prev, c_next = st.columns([1, 1, 1])
        with c_submit:
            submit = st.button(
                "提交答案",
                type="primary",
                key=f"seq_submit_{q['type']}_{q['id']}_{idx}",
                disabled=st.session_state.seq_submitted,
            )
        with c_prev:
            prev_clicked = st.button(
                "上一题",
                key=f"seq_prev_{q['type']}_{q['id']}_{idx}",
                disabled=idx == 0,
            )
        with c_next:
            next_clicked = st.button(
                "下一题",
                key=f"seq_next_{q['type']}_{q['id']}_{idx}",
                disabled=not st.session_state.seq_submitted,
            )

        if submit:
            if not choice:
                st.warning("请先选择答案。")
                return
            st.session_state.seq_submitted = True
            st.session_state.seq_last_choice = choice
            if not check_answer(choice, q["answer"]):
                record_wrong(q, choice)
            save_sequential_progress()
            st.rerun()

        if prev_clicked:
            st.session_state.seq_current_index = max(0, idx - 1)
            st.session_state.seq_submitted = False
            st.session_state.seq_last_choice = []
            save_sequential_progress()
            st.rerun()

        if next_clicked:
            st.session_state.seq_current_index += 1
            st.session_state.seq_submitted = False
            st.session_state.seq_last_choice = []
            save_sequential_progress()
            st.rerun()

        if st.session_state.seq_submitted:
            show_answer_result(q, st.session_state.seq_last_choice)

    with nav_col:
        render_sequential_navigation()


# ========== 模拟考试 ==========

def reset_exam() -> None:
    singles = [q for q in st.session_state.questions if q["type"] == "single"]
    multiples = [q for q in st.session_state.questions if q["type"] == "multiple"]
    if len(singles) < EXAM_SINGLE_COUNT or len(multiples) < EXAM_MULTIPLE_COUNT:
        raise ValueError("题库数量不足，无法生成模拟考试。")
    selected_singles = random.sample(singles, EXAM_SINGLE_COUNT)
    selected_multiples = random.sample(multiples, EXAM_MULTIPLE_COUNT)
    st.session_state.exam_order = [qkey(q) for q in selected_singles + selected_multiples]
    st.session_state.exam_current_index = 0
    st.session_state.exam_submitted = False
    st.session_state.exam_recorded_wrong = False
    st.session_state.exam_answers = {}
    st.session_state.exam_wrong_review_index = 0
    st.session_state.exam_wrong_review_submitted = False
    st.session_state.exam_wrong_review_last_choice = []
    save_exam_progress()


def restore_exam() -> None:
    progress = st.session_state.progress.get("exam", {})
    order = progress.get("order")
    if valid_order(order) and len(order) == EXAM_TOTAL_COUNT:
        st.session_state.exam_order = order
        st.session_state.exam_current_index = clamp_index(progress.get("current_index", 0), len(order))
        st.session_state.exam_submitted = bool(progress.get("submitted", False))
        st.session_state.exam_recorded_wrong = bool(progress.get("recorded_wrong", False))
        answers = progress.get("answers", {})
        st.session_state.exam_answers = answers if isinstance(answers, dict) else {}
        st.session_state.exam_wrong_review_index = int(progress.get("wrong_review_index", 0) or 0)
        st.session_state.exam_wrong_review_submitted = bool(progress.get("wrong_review_submitted", False))
        st.session_state.exam_wrong_review_last_choice = list(progress.get("wrong_review_last_choice", []))
    else:
        reset_exam()


def exam_part_label(index: int) -> str:
    if index < EXAM_SINGLE_COUNT:
        return f"单选第 {index + 1} 题"
    return f"多选第 {index - EXAM_SINGLE_COUNT + 1} 题"


def exam_display_index(index: int) -> int:
    return index + 1


def get_unanswered_exam_indices() -> list[int]:
    unanswered: list[int] = []
    for i, key in enumerate(st.session_state.exam_order):
        if not st.session_state.exam_answers.get(key):
            unanswered.append(i)
    return unanswered


def get_exam_scores_and_wrong_keys() -> tuple[int, int, int, list[str]]:
    single_score = 0
    multiple_score = 0
    wrong_keys: list[str] = []
    for key in st.session_state.exam_order:
        q = st.session_state.qmap[key]
        choice = st.session_state.exam_answers.get(key, [])
        if check_answer(choice, q["answer"]):
            if q["type"] == "single":
                single_score += 1
            else:
                multiple_score += 1
        else:
            wrong_keys.append(key)
    return single_score, multiple_score, single_score + multiple_score, wrong_keys


def render_exam_navigation() -> None:
    st.markdown("#### 题号导航")
    st.caption("点击题号可以跳转；✓ 表示已作答。")

    def render_button_grid(title: str, start: int, count: int, cols_count: int = 5) -> None:
        st.markdown(f"**{title}**")
        for row_start in range(0, count, cols_count):
            cols = st.columns(cols_count)
            for j, col in enumerate(cols):
                local_no = row_start + j + 1
                if local_no > count:
                    continue
                absolute_idx = start + local_no - 1
                key = st.session_state.exam_order[absolute_idx]
                answered = bool(st.session_state.exam_answers.get(key))
                is_current = absolute_idx == st.session_state.exam_current_index
                label = f"{'✓' if answered else ''}{local_no}"
                with col:
                    if st.button(
                        label,
                        key=f"exam_nav_{title}_{local_no}",
                        type="primary" if is_current else "secondary",
                        use_container_width=True,
                        disabled=st.session_state.exam_submitted,
                    ):
                        st.session_state.exam_current_index = absolute_idx
                        save_exam_progress()
                        st.rerun()

    render_button_grid("单选 1—70", 0, EXAM_SINGLE_COUNT)
    render_button_grid("多选 1—30", EXAM_SINGLE_COUNT, EXAM_MULTIPLE_COUNT)


def submit_exam_if_complete() -> None:
    unanswered = get_unanswered_exam_indices()
    if unanswered:
        st.warning(f"还有 {len(unanswered)} 道题未作答，不能提交试卷。请先完成所有题目。")
        preview = "、".join(exam_part_label(i) for i in unanswered[:15])
        if len(unanswered) > 15:
            preview += "……"
        st.info(f"未作答题目：{preview}")
        return
    st.session_state.exam_submitted = True
    st.session_state.exam_recorded_wrong = False
    save_exam_progress()
    st.rerun()


def render_exam_one_question() -> None:
    total = len(st.session_state.exam_order)
    idx = st.session_state.exam_current_index
    key = st.session_state.exam_order[idx]
    q = st.session_state.qmap[key]

    st.progress((idx + 1) / total)
    st.caption(f"当前：{idx + 1} / {total}｜{exam_part_label(idx)}｜原文第 {q['id']} 题")
    st.markdown(f"### 第 {idx + 1} 题｜{type_name(q['type'])}｜原文第 {q['id']} 题")
    st.write(q["question"])

    stored_choice = list(st.session_state.exam_answers.get(key, []))
    choice = render_answer_selector(
        q,
        key_prefix=f"exam_{key}_{idx}",
        stored_choice=stored_choice,
        disabled=False,
    )
    if choice != stored_choice:
        st.session_state.exam_answers[key] = choice
        save_exam_progress()

    c_prev, c_next, c_submit = st.columns([1, 1, 1])
    with c_prev:
        prev_clicked = st.button("上一题", key=f"exam_prev_{idx}", disabled=idx == 0)
    with c_next:
        next_clicked = st.button("下一题", key=f"exam_next_{idx}", disabled=idx >= total - 1)
    with c_submit:
        submit_clicked = st.button(
            "提交试卷" if idx == total - 1 else "到最后交卷",
            type="primary" if idx == total - 1 else "secondary",
            key=f"exam_submit_{idx}",
            disabled=idx != total - 1,
        )

    if prev_clicked:
        st.session_state.exam_current_index = max(0, idx - 1)
        save_exam_progress()
        st.rerun()

    if next_clicked:
        st.session_state.exam_current_index = min(total - 1, idx + 1)
        save_exam_progress()
        st.rerun()

    if submit_clicked:
        submit_exam_if_complete()

    if idx == total - 1:
        unanswered = get_unanswered_exam_indices()
        if unanswered:
            st.caption(f"当前仍有 {len(unanswered)} 道未作答，全部完成后才能提交试卷。")
        else:
            st.success("全部题目已作答，可以提交试卷。")


def render_exam_wrong_review(wrong_keys: list[str]) -> None:
    st.markdown("---")
    st.markdown("## 本次错题重做")
    if not wrong_keys:
        st.success("本次考试没有错题。")
        return

    idx = clamp_index(st.session_state.exam_wrong_review_index, len(wrong_keys))
    st.session_state.exam_wrong_review_index = idx
    key = wrong_keys[idx]
    q = st.session_state.qmap[key]
    original_idx = st.session_state.exam_order.index(key)

    main_col, nav_col = st.columns([4, 1], gap="large")
    with main_col:
        st.progress((idx + 1) / len(wrong_keys))
        st.caption(f"错题重做：{idx + 1} / {len(wrong_keys)}｜原试卷第 {original_idx + 1} 题｜{exam_part_label(original_idx)}")
        st.markdown(f"### 错题 {idx + 1}｜原试卷第 {original_idx + 1} 题｜原文第 {q['id']} 题")
        st.write(q["question"])
        st.caption(f"考试时你的答案：{format_options(q, st.session_state.exam_answers.get(key, []))}")

        choice = render_answer_selector(
            q,
            key_prefix=f"exam_wrong_redo_{key}_{idx}",
            stored_choice=st.session_state.exam_wrong_review_last_choice if st.session_state.exam_wrong_review_submitted else [],
            disabled=st.session_state.exam_wrong_review_submitted,
        )

        c_submit, c_prev, c_next = st.columns([1, 1, 1])
        with c_submit:
            submit = st.button(
                "提交答案",
                type="primary",
                key=f"exam_wrong_submit_{key}_{idx}",
                disabled=st.session_state.exam_wrong_review_submitted,
            )
        with c_prev:
            prev_clicked = st.button("上一题", key=f"exam_wrong_prev_{key}_{idx}", disabled=idx == 0)
        with c_next:
            next_clicked = st.button("下一题", key=f"exam_wrong_next_{key}_{idx}", disabled=idx >= len(wrong_keys) - 1)

        if submit:
            if not choice:
                st.warning("请先选择答案。")
                return
            st.session_state.exam_wrong_review_submitted = True
            st.session_state.exam_wrong_review_last_choice = choice
            save_exam_progress()
            st.rerun()

        if prev_clicked:
            st.session_state.exam_wrong_review_index = max(0, idx - 1)
            st.session_state.exam_wrong_review_submitted = False
            st.session_state.exam_wrong_review_last_choice = []
            save_exam_progress()
            st.rerun()

        if next_clicked:
            st.session_state.exam_wrong_review_index = min(len(wrong_keys) - 1, idx + 1)
            st.session_state.exam_wrong_review_submitted = False
            st.session_state.exam_wrong_review_last_choice = []
            save_exam_progress()
            st.rerun()

        if st.session_state.exam_wrong_review_submitted:
            show_answer_result(q, st.session_state.exam_wrong_review_last_choice, wrong_text="回答错误。请重点记忆。")

    with nav_col:
        render_exam_wrong_review_navigation(wrong_keys)


def render_exam_wrong_recap(wrong_keys: list[str]) -> None:
    st.markdown("---")
    st.markdown("## 本次错题回顾")
    if not wrong_keys:
        st.success("本次考试没有错题，无需回顾。")
        return
    st.caption("这里用于记忆复盘，会直接展示你的答案、正确答案和讲解。下面还可以逐题重做错题。")
    for n, key in enumerate(wrong_keys, start=1):
        q = st.session_state.qmap[key]
        original_idx = st.session_state.exam_order.index(key)
        with st.expander(f"错题 {n}｜原试卷第 {original_idx + 1} 题｜{type_name(q['type'])}｜原文第 {q['id']} 题"):
            st.write(q["question"])
            for letter, text in q["options"].items():
                st.write(f"{letter}. {text}")
            st.markdown(f"**你的考试答案：** {format_options(q, st.session_state.exam_answers.get(key, []))}")
            st.markdown(f"**正确答案：** {format_options(q, q['answer'])}")
            render_explanation(q["explanation"])


def render_exam_submitted() -> None:
    single_score, multiple_score, score, wrong_keys = get_exam_scores_and_wrong_keys()

    st.subheader("模拟考试结果")
    col_score, col_single, col_multi = st.columns(3)
    with col_score:
        st.metric("总分", f"{score} / 100")
    with col_single:
        st.metric("单选", f"{single_score} / {EXAM_SINGLE_COUNT}")
    with col_multi:
        st.metric("多选", f"{multiple_score} / {EXAM_MULTIPLE_COUNT}")
    st.caption(f"正确 {score} 道，错误 {len(wrong_keys)} 道。")

    if not st.session_state.exam_recorded_wrong:
        for key in wrong_keys:
            q = st.session_state.qmap[key]
            record_wrong(q, st.session_state.exam_answers.get(key, []))
        st.session_state.exam_recorded_wrong = True
        save_exam_progress()
        st.success("本次考试错题已加入错题本。")

    c_new, c_reset_redo = st.columns([1, 1])
    with c_new:
        if st.button("再考一套", type="primary"):
            reset_exam()
            st.rerun()
    with c_reset_redo:
        if wrong_keys and st.button("重新开始本次错题重做"):
            st.session_state.exam_wrong_review_index = 0
            st.session_state.exam_wrong_review_submitted = False
            st.session_state.exam_wrong_review_last_choice = []
            save_exam_progress()
            st.rerun()

    render_exam_wrong_recap(wrong_keys)
    render_exam_wrong_review(wrong_keys)


def render_exam() -> None:
    if not st.session_state.get("exam_order"):
        restore_exam()

    title_col, reset_col = st.columns([3, 1])
    with title_col:
        st.subheader("模拟考试")
    with reset_col:
        if st.button("重新生成试卷"):
            reset_exam()
            st.rerun()
    st.caption("第一部分 单项选择题 70 道；第二部分 多项选择题 30 道；一题一页；最后一题提交试卷。未全部作答不能提交。")

    if st.session_state.exam_submitted:
        render_exam_submitted()
        return

    main_col, nav_col = st.columns([4, 1], gap="large")
    with main_col:
        render_exam_one_question()
    with nav_col:
        render_exam_navigation()


# ========== 错题本 / 错题练习 ==========

def reset_wrong_practice(book: dict[str, Any] | None = None) -> None:
    book = book if book is not None else load_wrong_book()
    items = list(book.values())
    random.shuffle(items)
    st.session_state.wrong_order = [wrong_qkey(item) for item in items]
    st.session_state.wrong_current_index = 0
    st.session_state.wrong_submitted = False
    st.session_state.wrong_last_choice = []
    save_wrong_practice_progress()


def restore_wrong_practice(book: dict[str, Any]) -> None:
    progress = st.session_state.progress.get("wrong_practice", {})
    order = progress.get("order")
    if valid_wrong_order(order, book):
        st.session_state.wrong_order = order
        st.session_state.wrong_current_index = clamp_index(progress.get("current_index", 0), len(order))
        st.session_state.wrong_submitted = bool(progress.get("submitted", False))
        st.session_state.wrong_last_choice = list(progress.get("last_choice", []))
    else:
        reset_wrong_practice(book)


def render_wrong_practice(book: dict[str, Any]) -> None:
    if not st.session_state.get("wrong_order"):
        restore_wrong_practice(book)

    if not valid_wrong_order(st.session_state.wrong_order, book):
        reset_wrong_practice(book)

    total = len(st.session_state.wrong_order)
    idx = st.session_state.wrong_current_index

    if total == 0:
        st.success("暂无错题。")
        return

    if idx >= total:
        st.success("本轮错题已经全部练习完毕。")
        if st.button("重新练习错题", type="primary"):
            reset_wrong_practice(book)
            st.rerun()
        return

    key = st.session_state.wrong_order[idx]
    item = book[key]

    main_col, nav_col = st.columns([4, 1], gap="large")
    with main_col:
        st.progress((idx + 1) / total)
        st.caption(f"当前进度：{idx + 1} / {total}｜{type_name(item['type'])}｜原文第 {item['id']} 题｜历史答错 {item['wrong_count']} 次")
        st.markdown(f"### [{type_name(item['type'])}] 第 {item['id']} 题")
        st.write(item["question"])

        choice = render_answer_selector(
            item,
            key_prefix=f"wrong_{item['type']}_{item['id']}_{idx}",
            stored_choice=st.session_state.wrong_last_choice if st.session_state.wrong_submitted else [],
            disabled=st.session_state.wrong_submitted,
        )

        c_submit, c_prev, c_next = st.columns([1, 1, 1])
        with c_submit:
            submit = st.button(
                "提交答案",
                type="primary",
                key=f"wrong_submit_{item['type']}_{item['id']}_{idx}",
                disabled=st.session_state.wrong_submitted,
            )
        with c_prev:
            prev_clicked = st.button(
                "上一题",
                key=f"wrong_prev_{item['type']}_{item['id']}_{idx}",
                disabled=idx == 0,
            )
        with c_next:
            next_clicked = st.button(
                "下一题",
                key=f"wrong_next_{item['type']}_{item['id']}_{idx}",
                disabled=not st.session_state.wrong_submitted,
            )

        if submit:
            if not choice:
                st.warning("请先选择答案。")
                return
            st.session_state.wrong_submitted = True
            st.session_state.wrong_last_choice = choice
            if not check_answer(choice, item["answer"]):
                record_wrong(item, choice)
            save_wrong_practice_progress()
            st.rerun()

        if prev_clicked:
            st.session_state.wrong_current_index = max(0, idx - 1)
            st.session_state.wrong_submitted = False
            st.session_state.wrong_last_choice = []
            save_wrong_practice_progress()
            st.rerun()

        if next_clicked:
            st.session_state.wrong_current_index += 1
            st.session_state.wrong_submitted = False
            st.session_state.wrong_last_choice = []
            save_wrong_practice_progress()
            st.rerun()

        if st.session_state.wrong_submitted:
            show_answer_result(item, st.session_state.wrong_last_choice, wrong_text="回答错误。错题记录已更新。")

    with nav_col:
        render_wrong_navigation(book)


def render_wrong_details(book: dict[str, Any]) -> None:
    items = sorted(book.values(), key=lambda x: (x["type"], x["id"]))
    st.caption(f"共 {len(items)} 道错题。这里用于复盘记录，会直接显示正确答案；练习请切换到“错题练习”。")
    for item in items:
        with st.expander(f"[{type_name(item['type'])}] 第 {item['id']} 题｜答错 {item['wrong_count']} 次"):
            st.write(item["question"])
            for k, v in item["options"].items():
                st.write(f"{k}. {v}")
            st.markdown(f"**答错选项记录：** {', '.join(item['wrong_choices'])}")
            st.markdown(f"**正确答案：** {format_options(item, item['answer'])}")
            render_explanation(item["explanation"])
            st.caption(f"最后答错时间：{item.get('last_wrong_at', '')}")


def render_wrong_book() -> None:
    book = sync_wrong_book_with_questions(load_wrong_book(), st.session_state.qmap)
    title_col, reset_col = st.columns([3, 1])
    with title_col:
        st.subheader("错题本")
    with reset_col:
        if book and st.button("重新随机错题", key="wrong_top_reset"):
            reset_wrong_practice(book)
            st.rerun()

    if not book:
        st.success("暂无错题。")
        return

    mode = st.radio("错题本模式", ["错题练习", "错题记录"], horizontal=True)
    if mode == "错题练习":
        st.caption("错题练习默认隐藏答案；提交后才显示对错、正确答案和讲解。")
        render_wrong_practice(book)
    else:
        if st.button("清空错题本"):
            save_wrong_book({})
            st.session_state.wrong_order = []
            st.session_state.wrong_current_index = 0
            st.session_state.wrong_submitted = False
            st.session_state.wrong_last_choice = []
            save_wrong_practice_progress()
            st.rerun()
        render_wrong_details(book)


def reset_session_after_progress_clear() -> None:
    st.session_state.progress = default_progress()
    st.session_state.random_practice_type = None
    st.session_state.random_order = []
    st.session_state.random_current_index = 0
    st.session_state.random_submitted = False
    st.session_state.random_last_choice = []
    st.session_state.seq_order = []
    st.session_state.seq_current_index = 0
    st.session_state.seq_submitted = False
    st.session_state.seq_last_choice = []
    st.session_state.exam_order = []
    st.session_state.exam_current_index = 0
    st.session_state.exam_submitted = False
    st.session_state.exam_recorded_wrong = False
    st.session_state.exam_answers = {}
    st.session_state.exam_wrong_review_index = 0
    st.session_state.exam_wrong_review_submitted = False
    st.session_state.exam_wrong_review_last_choice = []
    st.session_state.wrong_order = []
    st.session_state.wrong_current_index = 0
    st.session_state.wrong_submitted = False
    st.session_state.wrong_last_choice = []


def main() -> None:
    st.set_page_config(page_title="入党积极分子在线刷题", page_icon="📘", layout="wide", initial_sidebar_state="collapsed")
    st.title("入党积极分子在线刷题")
    st.caption("题号与原文档一致；支持随机练习、顺序刷题、模拟考试、错题练习、错题记录和本机进度保存。")

    if "questions" not in st.session_state:
        st.session_state.questions = load_questions()
        st.session_state.qmap = {qkey(q): q for q in st.session_state.questions}
        st.session_state.progress = load_progress()
        st.session_state.random_practice_type = None
        st.session_state.random_order = []
        st.session_state.random_current_index = 0
        st.session_state.random_submitted = False
        st.session_state.random_last_choice = []
        st.session_state.seq_order = []
        st.session_state.seq_current_index = 0
        st.session_state.seq_submitted = False
        st.session_state.seq_last_choice = []
        st.session_state.exam_order = []
        st.session_state.exam_current_index = 0
        st.session_state.exam_submitted = False
        st.session_state.exam_recorded_wrong = False
        st.session_state.exam_answers = {}
        st.session_state.exam_wrong_review_index = 0
        st.session_state.exam_wrong_review_submitted = False
        st.session_state.exam_wrong_review_last_choice = []
        st.session_state.wrong_order = []
        st.session_state.wrong_current_index = 0
        st.session_state.wrong_submitted = False
        st.session_state.wrong_last_choice = []

    single_count = sum(q["type"] == "single" for q in st.session_state.questions)
    multiple_count = sum(q["type"] == "multiple" for q in st.session_state.questions)
    st.sidebar.metric("单选题", single_count)
    st.sidebar.metric("多选题", multiple_count)

    st.sidebar.markdown("---")
    st.sidebar.caption("本机进度会保存到 data/progress.json。关闭网页后重新打开，可继续上次进度。")
    if st.sidebar.button("清空本机进度"):
        clear_progress()
        reset_session_after_progress_clear()
        st.rerun()

    page = st.sidebar.radio("选择板块", ["随机单选题", "随机多选题", "顺序刷题", "模拟考试", "错题本"])
    if page == "随机单选题":
        render_random_practice("single")
    elif page == "随机多选题":
        render_random_practice("multiple")
    elif page == "顺序刷题":
        render_sequential_practice()
    elif page == "模拟考试":
        render_exam()
    else:
        render_wrong_book()


if __name__ == "__main__":
    main()
