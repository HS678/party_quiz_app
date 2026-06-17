from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "questions.json"

SINGLE_RANGES = [
    (1, 25, "党章总纲、党的性质、指导思想和二十大主题"),
    (26, 47, "社会主义初级阶段、基本路线和发展战略"),
    (48, 73, "民主政治、文化建设、安全生态、军队民族和外交"),
    (74, 100, "党的建设总体要求和党的领导"),
    (101, 115, "党员条件、党员义务和党员权利"),
    (116, 132, "发展党员、预备党员和党龄计算"),
    (133, 167, "组织生活、退党脱党和民主集中制"),
    (168, 190, "党的中央组织"),
    (191, 202, "党的地方组织"),
    (203, 220, "党的基层组织"),
    (221, 231, "党的干部"),
    (232, 256, "党的纪律和党纪处分"),
    (257, 274, "纪律检查委员会"),
    (275, 287, "党组、共青团和党徽党旗"),
    (288, 306, "党章发展历史"),
]

MULTI_RANGES = [
    (1, 9, "党的性质、习近平新时代中国特色社会主义思想、两个确立和两个维护"),
    (10, 17, "新发展理念、四个全面、改革开放和国家治理"),
    (18, 26, "政治制度、文化安全、强军、民族和外交"),
    (27, 40, "党的建设、伟大建党精神、四自能力和全面从严治党"),
    (41, 47, "党员权利义务、预备党员和组织制度"),
    (48, 52, "中央组织和地方组织"),
    (53, 60, "党的基层组织"),
    (61, 67, "党的干部和纪律处分"),
    (68, 73, "纪律检查委员会"),
    (74, 75, "党组"),
    (76, 78, "党的二十大综合重点"),
]

NEGATIVE_PATTERNS = ["不属于", "不包括", "错误的是", "不正确", "不是", "不能", "无权"]
CORRECT_PATTERNS = ["正确的是", "正确的", "符合", "包括", "职责", "任务", "职权"]

KEYWORDS = {
    "两个结合": "中国具体实际、中华优秀传统文化",
    "两个确立": "确立习近平同志党中央的核心、全党的核心地位，确立习近平新时代中国特色社会主义思想的指导地位",
    "两个维护": "维护习近平同志党中央的核心、全党的核心地位，维护党中央权威和集中统一领导",
    "四个意识": "政治意识、大局意识、核心意识、看齐意识",
    "四个自信": "道路自信、理论自信、制度自信、文化自信",
    "四个全面": "全面建设社会主义现代化国家、全面深化改革、全面依法治国、全面从严治党",
    "五位一体": "经济建设、政治建设、文化建设、社会建设、生态文明建设",
    "新发展理念": "创新、协调、绿色、开放、共享",
    "四项基本原则": "社会主义道路、人民民主专政、中国共产党领导、马克思列宁主义毛泽东思想",
    "民主集中制": "民主基础上的集中和集中指导下的民主相结合",
    "伟大建党精神": "坚持真理、坚守理想，践行初心、担当使命，不怕牺牲、英勇斗争，对党忠诚、不负人民",
    "群众路线": "一切为了群众，一切依靠群众，从群众中来，到群众中去",
    "三权": "表决权、选举权、被选举权",
    "六大纪律": "政治纪律、组织纪律、廉洁纪律、群众纪律、工作纪律、生活纪律",
    "五种处分": "警告、严重警告、撤销党内职务、留党察看、开除党籍",
    "纪律检查委员会": "党内监督专责机关，履行监督、执纪、问责职责",
    "党支部": "党的基础组织，直接教育、管理、监督党员并组织、宣传、凝聚、服务群众",
}

SPECIAL_TIPS = [
    ("预备党员", "预备党员常考四点：预备期 1 年、可延长但不超过 1 年、义务同正式党员一样、没有表决权/选举权/被选举权。"),
    ("党龄", "党龄从预备期满转为正式党员之日算起，不是从递交申请书或成为预备党员时算起。"),
    ("入党介绍人", "入党介绍人必须是 2 名正式党员；预备党员不能担任入党介绍人。"),
    ("支部大会", "涉及接收预备党员、转正、延长预备期、取消预备党员资格等事项，常见关键词是支部大会。"),
    ("留党察看", "留党察看最长不超过 2 年；期间没有表决权、选举权和被选举权。"),
    ("开除党籍", "开除党籍是党内最高处分，涉及严重违纪或严重触犯刑律。"),
    ("基层组织", "基层组织常考：正式党员 3 人以上应成立；基层委员会、总支部委员会、支部委员会任期 3 年至 5 年。"),
    ("中央委员会", "中央组织题要分清：全国代表大会选出中央委员会；中央委员会全会选举政治局、常委会和总书记。"),
    ("地方各级委员会", "地方组织题要分清：地方委员会全体会议闭会期间由常委会行使职权；地方全会每年至少召开 2 次。"),
    ("党组", "党组在非党组织的领导机关中成立，发挥领导核心作用，并服从批准其成立的党组织领导。"),
    ("共青团", "共青团是党的助手和后备军，是先进青年的群团组织。"),
    ("党徽", "党徽由镰刀和锤头组成；党旗是缀有金黄色党徽图案的红旗。"),
    ("党旗", "党徽由镰刀和锤头组成；党旗是缀有金黄色党徽图案的红旗。"),
]


def category(q: dict) -> str:
    ranges = SINGLE_RANGES if q["type"] == "single" else MULTI_RANGES
    for lo, hi, name in ranges:
        if lo <= int(q["id"]) <= hi:
            return name
    return "党章和党的基础知识"


def answer_text(q: dict) -> str:
    return "；".join(f"{k}. {q['options'][k]}" for k in q["answer"])


def option_analysis(q: dict, negative: bool) -> str:
    parts = []
    selected = set(q["answer"])
    for k, v in q["options"].items():
        if k in selected:
            if negative:
                parts.append(f"{k} 项是题干要求选出的不符合项/错误项：{v}。")
            else:
                parts.append(f"{k} 项正确：{v}，与本题固定表述一致。")
        else:
            if negative:
                parts.append(f"{k} 项属于干扰项，一般是符合题干背景的正确或相关表述，不是本题要选的错误项。")
            else:
                parts.append(f"{k} 项不选：表述、对象、时间、数字或概念与本题固定答案不一致。")
    return " ".join(parts)


def find_focus(q: dict) -> str:
    text = q["question"]
    hits = []
    for key, val in KEYWORDS.items():
        if key in text:
            hits.append(f"“{key}”对应：{val}")
    return "；".join(hits[:2])


def memory_tip(q: dict) -> str:
    text = q["question"] + " " + " ".join(q["options"].values())
    for keyword, tip in SPECIAL_TIPS:
        if keyword == "党组":
            if re.search(r"党组(?!织)", text):
                return tip
            continue
        if keyword in text:
            return tip
    ans = answer_text(q)
    if q["type"] == "multiple":
        return f"多选题要按成组概念记忆，本题答案组合是 {''.join(q['answer'])}，不要只记单个选项。"
    if any(ch.isdigit() for ch in ans) or "年" in ans or "月" in ans or "/" in ans:
        return f"本题属于数字/时间/比例题，直接把“{ans}”与题干关键词绑定记忆。"
    return f"把题干关键词和正确选项“{ans}”成对记忆，遇到相近表述时优先回到党章或题库原文。"


def make_explanation(q: dict) -> str:
    qid = q["id"]
    qtype_name = "单选" if q["type"] == "single" else "多选"
    ans_letters = "".join(q["answer"])
    cat = category(q)
    question_text = q["question"]
    negative = any(p in question_text for p in NEGATIVE_PATTERNS)
    stem_type = "本题是反向题，要求选出不符合/错误/不属于的一项。" if negative else "本题考查固定表述的准确识记。"
    focus = find_focus(q)
    focus_sentence = f"\n【关联知识】{focus}" if focus else ""
    return (
        f"【考点】{cat}。\n"
        f"【答案】{qtype_name}第 {qid} 题答案为 {ans_letters}：{answer_text(q)}。\n"
        f"【解析】{stem_type}正确答案来自题库原文答案标注，作答时要重点核对题干中的对象、时间、数字、机构名称和固定搭配。"
        f"{focus_sentence}\n"
        f"【选项辨析】{option_analysis(q, negative)}\n"
        f"【记忆提示】{memory_tip(q)}"
    )


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    for q in data:
        q["explanation"] = make_explanation(q)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"updated {len(data)} questions")


if __name__ == "__main__":
    main()
