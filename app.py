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


# ========== 基础数据读写 ==========

def load_questions() -> list[dict[str, Any]]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def load_wrong_book() -> dict[str, Any]:
    if not WRONG_FILE.exists():
        return {}
    return json.loads(WRONG_FILE.read_text(encoding="utf-8"))


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
        "id": q["id"],
        "type": q["type"],
        "question": q["question"],
        "options": q["options"],
        "answer": q["answer"],
        "explanation": q["explanation"],
        "wrong_count": 0,
        "wrong_choices": [],
        "last_wrong_at": "",
    })
    item["wrong_count"] += 1
    item["last_wrong_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    choice_text = "".join(sorted(choice)) if choice else "未选择"
    if choice_text not in item["wrong_choices"]:
        item["wrong_choices"].append(choice_text)
    book[key] = item
    save_wrong_book(book)


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
        "submitted": st.session_state.exam_submitted,
        "recorded_wrong": st.session_state.exam_recorded_wrong,
        "answers": st.session_state.exam_answers,
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
        st.session_state.random_current_index = min(int(progress.get("current_index", 0)), len(order))
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

    st.progress(idx / total)
    st.caption(f"当前进度：{idx + 1} / {total}，原文题号：第 {q['id']} 题")
    st.markdown(f"### 第 {q['id']} 题")
    st.write(q["question"])

    labels, label_to_key, _ = option_label_map(q)
    widget_key = f"random_choice_{qtype}_{q['id']}_{idx}"
    if qtype == "single":
        selected = st.radio("请选择一个答案：", labels, index=None, key=widget_key)
        choice = [label_to_key[selected]] if selected else []
    else:
        selected_list = st.multiselect("请选择一个或多个答案：", labels, key=widget_key)
        choice = [label_to_key[x] for x in selected_list]

    button_left, button_space, button_right = st.columns([1, 2, 1])
    with button_left:
        submit = st.button(
            "提交答案",
            type="primary",
            key=f"random_submit_{qtype}_{q['id']}_{idx}",
            disabled=st.session_state.random_submitted,
        )
    with button_right:
        next_clicked = st.button(
            "下一题",
            type="primary",
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

    if next_clicked:
        st.session_state.random_current_index += 1
        st.session_state.random_submitted = False
        st.session_state.random_last_choice = []
        save_random_progress()
        st.rerun()

    if st.session_state.random_submitted:
        user_choice = st.session_state.random_last_choice
        ok = check_answer(user_choice, q["answer"])
        if ok:
            st.success("回答正确！")
        else:
            st.error("回答错误。已加入错题本。")
        st.markdown(f"**你的答案：** {format_options(q, user_choice)}")
        st.markdown(f"**正确答案：** {format_options(q, q['answer'])}")
        st.info(q["explanation"])


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
        st.session_state.seq_current_index = min(int(progress.get("current_index", 0)), len(order))
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
    st.progress(idx / total)
    st.caption(f"当前进度：{idx + 1} / {total}｜{type_name(q['type'])}｜原文第 {q['id']} 题")
    st.markdown(f"### [{type_name(q['type'])}] 第 {q['id']} 题")
    st.write(q["question"])

    labels, label_to_key, _ = option_label_map(q)
    widget_key = f"seq_choice_{q['type']}_{q['id']}_{idx}"
    if q["type"] == "single":
        selected = st.radio("请选择一个答案：", labels, index=None, key=widget_key)
        choice = [label_to_key[selected]] if selected else []
    else:
        selected_list = st.multiselect("请选择一个或多个答案：", labels, key=widget_key)
        choice = [label_to_key[x] for x in selected_list]

    button_left, button_space, button_right = st.columns([1, 2, 1])
    with button_left:
        submit = st.button(
            "提交答案",
            type="primary",
            key=f"seq_submit_{q['type']}_{q['id']}_{idx}",
            disabled=st.session_state.seq_submitted,
        )
    with button_right:
        next_clicked = st.button(
            "下一题",
            type="primary",
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

    if next_clicked:
        st.session_state.seq_current_index += 1
        st.session_state.seq_submitted = False
        st.session_state.seq_last_choice = []
        save_sequential_progress()
        st.rerun()

    if st.session_state.seq_submitted:
        user_choice = st.session_state.seq_last_choice
        ok = check_answer(user_choice, q["answer"])
        if ok:
            st.success("回答正确！")
        else:
            st.error("回答错误。已加入错题本。")
        st.markdown(f"**你的答案：** {format_options(q, user_choice)}")
        st.markdown(f"**正确答案：** {format_options(q, q['answer'])}")
        st.info(q["explanation"])


# ========== 模拟考试 ==========

def reset_exam() -> None:
    singles = [q for q in st.session_state.questions if q["type"] == "single"]
    multiples = [q for q in st.session_state.questions if q["type"] == "multiple"]
    if len(singles) < EXAM_SINGLE_COUNT or len(multiples) < EXAM_MULTIPLE_COUNT:
        raise ValueError("题库数量不足，无法生成模拟考试。")
    # 模拟考试要求：前 70 题为单选，后 30 题为多选。
    # 单选内部随机抽取、随机排序；多选内部随机抽取、随机排序；不再对整张试卷整体打乱。
    selected_singles = random.sample(singles, EXAM_SINGLE_COUNT)
    selected_multiples = random.sample(multiples, EXAM_MULTIPLE_COUNT)
    st.session_state.exam_order = [qkey(q) for q in selected_singles + selected_multiples]
    st.session_state.exam_submitted = False
    st.session_state.exam_recorded_wrong = False
    st.session_state.exam_answers = {}
    save_exam_progress()


def restore_exam() -> None:
    progress = st.session_state.progress.get("exam", {})
    order = progress.get("order")
    if valid_order(order) and len(order) == EXAM_SINGLE_COUNT + EXAM_MULTIPLE_COUNT:
        st.session_state.exam_order = order
        st.session_state.exam_submitted = bool(progress.get("submitted", False))
        st.session_state.exam_recorded_wrong = bool(progress.get("recorded_wrong", False))
        answers = progress.get("answers", {})
        st.session_state.exam_answers = answers if isinstance(answers, dict) else {}
    else:
        reset_exam()


def render_exam() -> None:
    if not st.session_state.get("exam_order"):
        restore_exam()

    st.subheader("模拟考试")
    st.caption("随机抽取单选 70 道、多选 30 道；每题 1 分，满分 100 分。提交整张试卷后显示成绩、正确答案和讲解。")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.metric("试卷题量", f"{len(st.session_state.exam_order)} 道")
    with col2:
        st.metric("满分", "100 分")

    if st.button("重新生成试卷"):
        reset_exam()
        st.rerun()

    answers: dict[str, list[str]] = dict(st.session_state.exam_answers)
    unanswered = 0
    answers_changed = False

    def render_exam_section(title: str, keys: list[str], start_index: int) -> None:
        nonlocal unanswered, answers_changed
        st.markdown("---")
        st.markdown(f"## {title}")
        for offset, key in enumerate(keys):
            i = start_index + offset
            q = st.session_state.qmap[key]
            with st.expander(f"第 {i} 题｜{type_name(q['type'])}｜原文第 {q['id']} 题", expanded=not st.session_state.exam_submitted):
                st.write(q["question"])
                labels, label_to_key, key_to_label = option_label_map(q)
                stored_choice = [x for x in answers.get(key, []) if x in q["options"]]
                widget_key = f"exam_choice_{key}_{i}"
                if q["type"] == "single":
                    default_index = None
                    if stored_choice:
                        stored_label = key_to_label.get(stored_choice[0])
                        if stored_label in labels:
                            default_index = labels.index(stored_label)
                    selected = st.radio(
                        "请选择一个答案：",
                        labels,
                        index=default_index,
                        key=widget_key,
                        disabled=st.session_state.exam_submitted,
                    )
                    choice = [label_to_key[selected]] if selected else []
                else:
                    default_labels = [key_to_label[x] for x in stored_choice if x in key_to_label]
                    selected_list = st.multiselect(
                        "请选择一个或多个答案：",
                        labels,
                        default=default_labels,
                        key=widget_key,
                        disabled=st.session_state.exam_submitted,
                    )
                    choice = [label_to_key[x] for x in selected_list]
                answers[key] = choice
                if choice != st.session_state.exam_answers.get(key, []):
                    answers_changed = True
                if not choice:
                    unanswered += 1

                if st.session_state.exam_submitted:
                    ok = check_answer(choice, q["answer"])
                    if ok:
                        st.success("正确")
                    else:
                        st.error("错误")
                    st.markdown(f"**你的答案：** {format_options(q, choice)}")
                    st.markdown(f"**正确答案：** {format_options(q, q['answer'])}")
                    st.info(q["explanation"])

    single_keys = st.session_state.exam_order[:EXAM_SINGLE_COUNT]
    multiple_keys = st.session_state.exam_order[EXAM_SINGLE_COUNT:]
    render_exam_section(f"第一部分 单项选择题（共 {EXAM_SINGLE_COUNT} 题）", single_keys, 1)
    render_exam_section(f"第二部分 多项选择题（共 {EXAM_MULTIPLE_COUNT} 题）", multiple_keys, EXAM_SINGLE_COUNT + 1)

    st.session_state.exam_answers = answers
    if answers_changed:
        save_exam_progress()

    if not st.session_state.exam_submitted:
        st.caption(f"未作答：{unanswered} 道。未作答题目提交后按错误处理。")
        if st.button("提交试卷", type="primary"):
            st.session_state.exam_submitted = True
            save_exam_progress()
            st.rerun()
    else:
        single_score = 0
        multiple_score = 0
        wrong_items: list[tuple[dict[str, Any], list[str]]] = []
        for key in st.session_state.exam_order:
            q = st.session_state.qmap[key]
            choice = answers.get(key, [])
            if check_answer(choice, q["answer"]):
                if q["type"] == "single":
                    single_score += 1
                else:
                    multiple_score += 1
            else:
                wrong_items.append((q, choice))
        score = single_score + multiple_score
        st.markdown("---")
        st.metric("本次模拟考试成绩", f"{score} / 100")
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("单选得分", f"{single_score} / {EXAM_SINGLE_COUNT}")
        with col_b:
            st.metric("多选得分", f"{multiple_score} / {EXAM_MULTIPLE_COUNT}")
        st.caption(f"正确 {score} 道，错误 {100 - score} 道。")
        if not st.session_state.exam_recorded_wrong:
            for q, choice in wrong_items:
                record_wrong(q, choice)
            st.session_state.exam_recorded_wrong = True
            save_exam_progress()
            st.success("本次考试错题已加入错题本。")
        if st.button("再考一套", type="primary"):
            reset_exam()
            st.rerun()


# ========== 错题本 ==========

def render_wrong_book() -> None:
    st.subheader("错题本")
    book = load_wrong_book()
    if not book:
        st.success("暂无错题。")
        return

    items = sorted(book.values(), key=lambda x: (x["type"], x["id"]))
    st.caption(f"共 {len(items)} 道错题。")
    if st.button("清空错题本"):
        save_wrong_book({})
        st.rerun()

    for item in items:
        with st.expander(f"[{type_name(item['type'])}] 第 {item['id']} 题｜答错 {item['wrong_count']} 次"):
            st.write(item["question"])
            for k, v in item["options"].items():
                st.write(f"{k}. {v}")
            st.markdown(f"**答错选项记录：** {', '.join(item['wrong_choices'])}")
            st.markdown(f"**正确答案：** {format_options(item, item['answer'])}")
            st.info(item["explanation"])
            st.caption(f"最后答错时间：{item.get('last_wrong_at', '')}")


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
    st.session_state.exam_submitted = False
    st.session_state.exam_recorded_wrong = False
    st.session_state.exam_answers = {}


def main() -> None:
    st.set_page_config(page_title="入党积极分子在线刷题", page_icon="📘", layout="centered")
    st.title("入党积极分子在线刷题")
    st.caption("题号与原文档一致；支持随机练习、顺序刷题、模拟考试、错题本和本机进度保存。")

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
        st.session_state.exam_submitted = False
        st.session_state.exam_recorded_wrong = False
        st.session_state.exam_answers = {}

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
