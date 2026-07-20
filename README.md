# what-to-eat

帮你决定这顿吃什么。调用 DeepSeek V4 Pro（思考模式），每次通过随机约束 + 日期时间 + 历史去重让模型给出不同的推荐。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 在同目录创建 apikey.txt，写入 DeepSeek API Key
echo sk-xxxxxxxx > apikey.txt

# 3. 运行
python what_to_eat.py
```

API Key 获取：https://platform.deepseek.com/api_keys

## 输出示例

```
约束: 性价比高 | 东南亚风味 | 下饭的
思考中...

>>> [泰式打抛猪肉饭]
酸辣开胃，肉末拌饭简直停不下来，一份30以内搞定。
```

## 怎么做到每次不同

| 机制 | 说明 |
|---|---|
| 随机约束 | 27 个约束（价格/口味/类型/场景/营养/猎奇），每次随机抽 2-3 个 |
| 日期时间 | 当前日期、星期、时辰、早中晚餐时段自然变化 |
| 随机语气 | 每次从"简洁/热情/幽默/美食家"中随机选一种 |
| 历史去重 | 最近 7 次推荐传给模型要求避开，历史存 `history.json` |

## 自定义

编辑 `what_to_eat.py` 顶部 `CONSTRAINTS` 列表，增减你喜欢的约束词。

## 依赖

- Python 3.10+
- openai >= 1.0.0
