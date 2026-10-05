#!/usr/bin/env python3
"""
what-to-eat — 帮你决定这顿吃什么。

每次调用 DeepSeek V4 Pro（思考模式），通过随机约束 + 日期时间 + 历史去重
让模型给出不同的推荐。输出格式为 [食物名称]，脚本解析后显示。
"""

import json
import random
import re
import sys
from datetime import datetime
from pathlib import Path

from openai import OpenAI

# ── 配置 ──────────────────────────────────────────────

MODEL = "deepseek-v4-pro"
BASE_URL = "https://api.deepseek.com"
SCRIPT_DIR = Path(__file__).parent
API_KEY_FILE = SCRIPT_DIR / "apikey.txt"
HISTORY_FILE = SCRIPT_DIR / "history.json"
HISTORY_KEEP = 30

# ── 随机约束池 ────────────────────────────────────────

CONSTRAINTS = [
    # 价格维度
    "30元以内", "豪华一点放纵一下", "性价比高",
    # 口味维度
    "辣的", "清淡的", "酸甜口", "咸香的", "蒜香味的", "麻的",
    # 类型维度
    "中式快餐", "日料", "韩餐", "西式简餐", "东南亚风味",
    "面食", "米饭类", "饺子馄饨", "粥粉面饭",
    "烧烤", "火锅", "麻辣烫/冒菜", "轻食沙拉",
    "地方特色小吃", "港式茶餐厅", "汉堡炸鸡",
    # 场景维度
    "适合夏天吃", "暖胃的", "吃完不犯困",
    "能带走的", "适合一个人吃", "下饭的",
    # 营养维度
    "高蛋白", "多蔬菜", "碳水快乐",
    # 猎奇维度
    "平时不常吃的", "异国料理",
]

def load_api_key() -> str:
    """从脚本同目录下的 apikey.txt 读取 API Key。"""
    if not API_KEY_FILE.exists():
        sys.exit(
            f"错误：未找到 API Key 文件。\n"
            f"请在 {API_KEY_FILE} 中写入你的 DeepSeek API Key。\n"
            f"获取 Key：https://platform.deepseek.com/api_keys"
        )
    key = API_KEY_FILE.read_text(encoding="utf-8").strip()
    if not key:
        sys.exit(f"错误：{API_KEY_FILE} 内容为空，请填入 API Key。")
    return key


# ── 历史缓存（模块级，避免重复读文件） ────────────────

_history: list[dict] | None = None


def load_history() -> list[dict]:
    global _history
    if _history is not None:
        return _history
    if HISTORY_FILE.exists():
        try:
            _history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return _history
        except (json.JSONDecodeError, OSError):
            pass
    _history = []
    return _history


def save_history(history: list[dict]) -> None:
    global _history
    _history = history[-HISTORY_KEEP:]
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(_history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── prompt 构造 ───────────────────────────────────────

def build_prompt(constraints: list[str], recent: list[str], extra: str | None) -> str:
    now = datetime.now()
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
    hour = now.hour
    if hour < 10:
        meal = "早餐"
    elif hour < 15:
        meal = "午餐"
    elif hour < 21:
        meal = "晚餐"
    else:
        meal = "夜宵"

    # 生成随机的标注风格，让输出格式每次都略有不同
    flavor = random.choice(["简洁", "热情", "幽默", "像个美食家"])

    lines = [
        f"现在是{now.strftime('%Y年%m月%d日')} {weekday} {now.hour}:{now.minute:02d}，我想吃{meal}。",
        f"请以{flavor}的语气，根据以下条件推荐一样具体的食物（要具体到菜品名，不要说笼统的分类）：",
        *(f"- {c}" for c in constraints),
    ]
    if extra:
        lines.append(f"附加要求：{extra}")
    if recent:
        lines.append(
            f"注意：最近已经吃过/被推荐过这些：{'、'.join(recent)}，请务必推荐不一样的。"
        )
    lines.append(
        "用方括号标注你推荐的食物，例如 [黄焖鸡米饭]。方括号后可以加一两句简短理由。"
    )
    return "\n".join(lines)


# ── 解析 ──────────────────────────────────────────────

def parse_result(text: str) -> str | None:
    match = re.search(r"\[(.+?)\]", text)
    return match.group(1).strip() if match else None


# ── 单次推荐 ──────────────────────────────────────────

def recommend(client: OpenAI, extra: str | None) -> None:
    """执行一次推荐并打印结果。extra 为用户附加要求。"""

    # 1. 随机抽 2-3 个约束
    constraints = random.sample(CONSTRAINTS, k=random.randint(2, 3))

    # 2. 加载历史
    history = load_history()
    recent = [h["food"] for h in history[-7:]]

    # 3. 构造 prompt
    prompt = build_prompt(constraints, recent, extra)

    print(f"\n约束: {' | '.join(constraints)}")
    print("思考中...", flush=True)

    # 4. 调用 DeepSeek V4 Pro（思考模式）
    #    注意 reasoning_effort 现在写在 thinking 对象里，不再是顶层参数
    #    （见 API 文档 create-chat-completion 的参数表）。thinking 不是 OpenAI SDK
    #    认识的字段，直接当关键字参数传会被 SDK 拦下，必须走 extra_body 并入请求体。
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        extra_body={"thinking": {"type": "enabled", "reasoning_effort": "high"}},
    )

    answer = response.choices[0].message.content or ""
    reasoning = getattr(response.choices[0].message, "reasoning_content", None)

    # 5. 解析结果
    food = parse_result(answer)

    if food:
        if reasoning:
            print(f"\n[思考] {reasoning[:200]}{'…' if len(reasoning) > 200 else ''}\n")
        print(f">>> [{food}]")
        remaining = answer.replace(f"[{food}]", "").strip()
        if remaining:
            print(remaining)
        # 记录历史
        history.append({
            "time": datetime.now().isoformat(timespec="seconds"),
            "food": food,
            "constraints": constraints,
        })
        save_history(history)
    else:
        print(f"未能解析推荐结果，原始回复：\n{answer}")


# ── 主流程 ─────────────────────────────────────────────

def main():
    api_key = load_api_key()
    client = OpenAI(api_key=api_key, base_url=BASE_URL)

    print("=== what-to-eat ===")
    print("按回车获取推荐，输入附加要求后回车，输入 q 退出")

    while True:
        cmd = input("> ").strip()
        if cmd.lower() == "q":
            print("再见！")
            break
        recommend(client, cmd if cmd else None)


if __name__ == "__main__":
    main()
