"""
脚本生成模块 - 调用 DeepSeek API 生成结构化短视频脚本

输出示例:
{
  "title": "什么是量子计算？",
  "bgm_style": "科技感、轻快",
  "scenes": [
    {
      "narration": "量子计算是一种利用量子力学原理...",
      "image_prompt": "抽象风格、量子比特、3D渲染、蓝色紫色",
      "keywords": ["量子计算", "量子比特"]
    }
  ],
  "outro_text": "关注我，每天一个科技小知识"
}
"""

import json
from pathlib import Path
from typing import Optional

from openai import OpenAI

from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    SCRIPT_DIR,
)
from utils import save_json, slugify


# DeepSeek OpenAI 兼容客户端
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )
    return _client


# 脚本生成 prompt
SCRIPT_SYSTEM_PROMPT = """你是一个专业的短视频脚本作家，擅长为知识科普类短视频撰写脚本。

请根据用户提供的主题，生成一份结构化的短视频脚本，以 JSON 格式输出。
所有文字内容必须使用简体中文，禁止使用繁体中文。

## 输出格式要求
```json
{
  "title": "视频标题（15字以内，吸引人，简体中文）",
  "bgm_style": "背景音乐风格描述",
  "scenes": [
    {
      "narration": "当前段落旁白文字（30-60字，口语化，适合配音，简体中文）",
      "image_prompt": "配图生成提示词（50字以内，描述画面内容、风格、色调）",
      "keywords": ["关键词1", "关键词2"]
    }
  ],
  "outro_text": "片尾引导文案（简体中文）"
}
```

## 写作要求
1. 总时长控制在 45-90 秒，建议 5-8 个分镜
2. 每个分镜的旁白 30-60 字，口语化，通俗易懂
3. image_prompt 描述画面时包含风格、色调、画面元素
4. 整体结构：开场引入 -> 核心知识点 -> 举例说明 -> 总结升华
5. 每句旁白末尾标点使用句号，方便 TTS 断句
6. 请只输出 JSON，不要包含其他内容
7. 务必使用简体中文，不要出现繁体字"""


def generate_script(topic: str, custom_prompt: Optional[str] = None) -> dict:
    """
    根据主题生成短视频脚本

    Args:
        topic: 视频主题
        custom_prompt: 可选的自定义补充要求

    Returns:
        结构化脚本 dict
    """
    client = _get_client()

    user_content = f"请为一个知识科普短视频创作脚本。主题是：{topic}"
    if custom_prompt:
        user_content += f"\n\n额外要求：{custom_prompt}"

    print(f"[AI] 正在调用 DeepSeek 生成脚本...")
    print(f"   主题: {topic}")

    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": SCRIPT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.7,
        max_tokens=4096,
    )

    content = response.choices[0].message.content.strip()

    # 清理可能的 markdown 代码块标记
    if content.startswith("```json"):
        content = content[7:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    script = json.loads(content)

    # 验证必要字段
    assert "title" in script, "脚本缺少 title"
    assert "scenes" in script and len(script["scenes"]) > 0, "脚本缺少 scenes"

    # 保存到文件
    safe_name = slugify(topic)
    filepath = SCRIPT_DIR / f"{safe_name}.json"
    save_json(script, filepath)
    print(f"[OK] 脚本已生成: {filepath}")
    print(f"   标题: {script['title']}")
    print(f"   分镜数: {len(script['scenes'])}")

    return script


if __name__ == "__main__":
    # 测试
    script = generate_script("什么是量子纠缠？")
    print(json.dumps(script, ensure_ascii=False, indent=2))
