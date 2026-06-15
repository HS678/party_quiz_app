from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from docx import Document
except ImportError as exc:
    raise SystemExit("请先安装 python-docx：pip install python-docx") from exc

QUESTION_RE = re.compile(r"^\s*(\d+)\s*[\.,．、]\s*(.+)$")
OPTION_RE = re.compile(r"^\s*([A-D])(?:[\.．、]|\s+)(.+)$")
ANSWER_RE = re.compile(r"[（\(]\s*([A-D](?:\s*[A-D]){0,3})\s*[）\)]")
SECTION_SINGLE = "单项选择题"
SECTION_MULTI = "多项选择题"


def normalize_answer(ans: str) -> list[str]:
    return sorted(set(re.findall(r"[A-D]", ans.upper())))


def remove_answer_from_question(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        letters = normalize_answer(match.group(1))
        if letters:
            return "(    )"
        return match.group(0)
    return ANSWER_RE.sub(repl, text).strip()


def extract_answer(text: str) -> list[str]:
    matches = ANSWER_RE.findall(text)
    if not matches:
        return []
    # 题干里可能有多个空，取真正含 A-D 的答案串；通常只有一个。
    for m in matches:
        ans = normalize_answer(m)
        if ans:
            return ans
    return []


def read_docx_paragraphs(path: Path) -> list[str]:
    doc = Document(str(path))
    return [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]


def parse_questions(paragraphs: list[str]) -> list[dict[str, Any]]:
    section = None
    current: dict[str, Any] | None = None
    questions: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        current["answer"] = extract_answer(current["raw_question"])
        current["question"] = remove_answer_from_question(current["raw_question"])
        current["explanation"] = (
            f"本题来自原题库第 {current['id']} 题。正确答案为 "
            f"{''.join(current['answer'])}。请重点记忆题干中的关键词与正确选项表述。"
        )
        questions.append(current)
        current = None

    for para in paragraphs:
        if SECTION_SINGLE in para and len(para) < 30:
            flush()
            section = "single"
            continue
        if SECTION_MULTI in para and len(para) < 30:
            flush()
            section = "multiple"
            continue
        if section not in {"single", "multiple"}:
            continue

        qm = QUESTION_RE.match(para)
        om = OPTION_RE.match(para)
        if qm:
            flush()
            qid = int(qm.group(1))
            current = {
                "id": qid,
                "type": section,
                "raw_question": qm.group(2).strip(),
                "options": {},
            }
            continue
        if om and current:
            key = om.group(1).upper()
            current["options"][key] = om.group(2).strip()
            continue
        # 兼容极少数自动换行导致的续行
        if current:
            if current["options"]:
                last_key = sorted(current["options"].keys())[-1]
                current["options"][last_key] += para.strip()
            else:
                current["raw_question"] += para.strip()

    flush()
    return questions


def validate_questions(questions: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen = set()
    by_type = {"single": [], "multiple": []}
    for q in questions:
        key = (q["type"], q["id"])
        if key in seen:
            errors.append(f"重复题号：{q['type']} {q['id']}")
        seen.add(key)
        by_type[q["type"]].append(q)
        if not q["answer"]:
            errors.append(f"缺少答案：{q['type']} {q['id']}")
        if not set(q["answer"]).issubset(q["options"].keys()):
            errors.append(f"答案与选项不匹配：{q['type']} {q['id']} answer={q['answer']} options={list(q['options'])}")
        if q["type"] == "single" and len(q["answer"]) != 1:
            errors.append(f"单选题答案不是 1 个：{q['id']} {q['answer']}")
        if q["type"] == "multiple" and len(q["answer"]) < 2:
            errors.append(f"多选题答案少于 2 个：{q['id']} {q['answer']}")
        expected = 3 if q["type"] == "single" else 4
        if len(q["options"]) != expected:
            errors.append(f"选项数量异常：{q['type']} {q['id']} count={len(q['options'])}")
    for typ, arr in by_type.items():
        ids = [q["id"] for q in arr]
        if ids and ids != list(range(1, max(ids) + 1)):
            errors.append(f"{typ} 题号不连续：min={min(ids)} max={max(ids)} count={len(ids)}")
    return errors


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "source" / "入党积极分子题库答案第一版.docx"
    out = root / "data" / "questions.json"
    if not source.exists():
        raise SystemExit(f"未找到源文件：{source}")
    questions = parse_questions(read_docx_paragraphs(source))
    errors = validate_questions(questions)
    if errors:
        raise SystemExit("题库校验失败：\n" + "\n".join(errors[:80]))
    out.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
    single = sum(q["type"] == "single" for q in questions)
    multiple = sum(q["type"] == "multiple" for q in questions)
    print(f"已生成 {out}")
    print(f"单选题：{single}；多选题：{multiple}；总题数：{len(questions)}")


if __name__ == "__main__":
    main()
