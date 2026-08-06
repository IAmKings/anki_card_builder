"""Shared AI-powered multiple-choice distractor & hint generator.

Domain-agnostic — call from any Anki deck generator script with a list of
knowledge points (dicts with number/keyword/explanation).

Usage:
    from src.ai_mc_generator import generate_mc_data

    mc_data = generate_mc_data(
        points=[{"number": 1, "keyword": "MQTT", "explanation": "..."}, ...],
        domain="MQTT 协议",
        api_key="sk-xxx",
        api_model="deepseek-chat",
        api_provider="deepseek",
    )
    # mc_data = {1: {"distractors": [...], "hint": "..."}, ...}

Without --ai flag, the caller should skip this module entirely (no API cost).
"""

import json
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional

import requests  # type: ignore[import-untyped]

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BATCH_SIZE = 12
API_MAX_RETRIES = 3
API_MAX_TOKENS = 10000
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def _build_prompt(points: List[Dict[str, Any]], domain: str) -> str:
    """Build the shared prompt for AI batch generation."""
    lines = [
        f"请为以下 {domain} 知识点批量生成选择题干扰项与学习提示。",
        "每个知识点给出了正确答案，请生成 3 个与正确答案相似但错误的干扰项，",
        "以及一条不超过 150 字的扩展提示。",
        "干扰项必须是可能被误选的相关描述，彼此不同且与正确答案不同。",
        "只输出 JSON 数组，不要包含其他内容，格式：",
        '[{"number": 序号, "distractors": ["干扰项1", "干扰项2", "干扰项3"],'
        ' "hint": "扩展提示"}]',
    ]
    for point in points:
        explanation = str(point.get("explanation", ""))
        if len(explanation) > 300:
            explanation = explanation[:299].rstrip() + "…"
        lines.append(
            f"序号 {point.get('number', '?')}；"
            f"关键词：{point.get('keyword', '')}；"
            f"正确答案：{explanation}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _parse_response(text: str) -> Optional[List[Dict[str, Any]]]:
    """Parse the JSON response from any AI API into the standard format."""
    match = re.search(r"\[[\s\S]*\]", text)
    try:
        data = json.loads(match.group(0)) if match else json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


# ---------------------------------------------------------------------------
# API callers
# ---------------------------------------------------------------------------


def _call_deepseek(
    prompt: str, api_key: str, api_model: str
) -> Optional[List[Dict[str, Any]]]:
    """Call the DeepSeek API (OpenAI-compatible) for one batch."""
    for attempt in range(API_MAX_RETRIES):
        try:
            resp = requests.post(
                DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": api_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": API_MAX_TOKENS,
                    "temperature": 0.7,
                },
                timeout=60,
            )
            if resp.status_code != 200:
                log.warning(
                    "DeepSeek API 返回 %d: %s",
                    resp.status_code,
                    resp.text[:200],
                )
                if attempt < API_MAX_RETRIES - 1:
                    time.sleep(2 * (attempt + 1))
                continue
            body = resp.json()
            text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not text:
                log.warning("DeepSeek API 返回内容为空")
                return None
            result = _parse_response(text)
            if result:
                return result
            log.warning("DeepSeek API 返回 JSON 解析失败")
            return None
        except Exception as exc:  # pylint: disable=broad-except
            log.warning("DeepSeek API 调用失败（第 %d 次）: %s", attempt + 1, exc)
            if attempt < API_MAX_RETRIES - 1:
                time.sleep(2 * (attempt + 1))
    return None


def _call_claude(
    prompt: str, api_key: str, api_model: str
) -> Optional[List[Dict[str, Any]]]:
    """Call the Claude API for one batch of knowledge points."""
    try:
        from anthropic import Anthropic  # pylint: disable=import-outside-toplevel
    except ImportError:
        log.warning("anthropic 未安装，无法调用 Claude API")
        return None

    client = Anthropic(api_key=api_key)

    for attempt in range(API_MAX_RETRIES):
        try:
            response = client.messages.create(
                model=api_model,
                max_tokens=API_MAX_TOKENS,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )
            text_parts = [getattr(block, "text", "") for block in response.content]
            result = "\n".join(part for part in text_parts if part)
            if not result:
                log.warning("Claude API 返回内容中没有文本块")
                return None
            parsed = _parse_response(result)
            if parsed:
                return parsed
            return None
        except Exception as exc:  # pylint: disable=broad-except
            log.warning("Claude API 调用失败（第 %d 次）: %s", attempt + 1, exc)
            if attempt < API_MAX_RETRIES - 1:
                time.sleep(2 * (attempt + 1))
    return None


# ---------------------------------------------------------------------------
# Response processing
# ---------------------------------------------------------------------------


def _process_ai_items(
    response: List[Dict[str, Any]], result: Dict[int, Dict[str, Any]]
) -> None:
    """Extract distractors and hints from AI response into the result dict."""
    for item in response:
        number_value = item.get("number")
        if isinstance(number_value, bool):
            continue
        if isinstance(number_value, int):
            number = number_value
        elif isinstance(number_value, str) and number_value.isdigit():
            number = int(number_value)
        else:
            continue
        distractors = item.get("distractors", [])
        if not isinstance(distractors, list):
            distractors = []
        hint = item.get("hint", "")
        result[number] = {
            "distractors": [str(d) for d in distractors],
            "hint": str(hint),
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_mc_data(
    points: List[Dict[str, Any]],
    domain: str = "",
    api_key: str = "",
    api_model: str = "deepseek-chat",
    api_provider: str = "deepseek",
) -> Dict[int, Dict[str, Any]]:
    """Generate MC distractors + hints via AI APIs.

    Args:
        points: List of dicts with keys {number, keyword, explanation}.
        domain: Domain name for prompt context (e.g. "MQTT 协议").
        api_key: API key for the chosen provider.
        api_model: Model name (e.g. "deepseek-chat", "claude-sonnet-4-20250514").
        api_provider: "deepseek" or "claude".

    Returns:
        Dict keyed by knowledge-point number:
        {number: {"distractors": [...], "hint": "..."}}.
        Empty dict when API is unavailable — caller should use fallback.
    """
    result: Dict[int, Dict[str, Any]] = {}

    if not api_key:
        log.warning("%s API key 未配置，跳过 AI 生成", api_provider)
        return result

    if api_provider == "deepseek":
        log.info("  使用 DeepSeek API 生成选择题")
        call_fn: Callable = _call_deepseek
    elif api_provider == "claude":
        log.info("  使用 Claude API 生成选择题")
        call_fn = _call_claude
    else:
        log.warning("不支持的 API provider: %s", api_provider)
        return result

    total_batches = (len(points) + API_BATCH_SIZE - 1) // API_BATCH_SIZE
    for index in range(0, len(points), API_BATCH_SIZE):
        batch = points[index : index + API_BATCH_SIZE]
        batch_no = index // API_BATCH_SIZE + 1
        first_num = batch[0].get("number", "?")
        last_num = batch[-1].get("number", "?")
        log.info("  AI 批 %d/%d: 知识点 %s-%s", batch_no, total_batches, first_num, last_num)

        prompt = _build_prompt(batch, domain)
        response = call_fn(prompt, api_key, api_model)
        if not response:
            log.warning("  AI 批 %d 失败，该批使用 fallback 干扰项", batch_no)
            continue
        _process_ai_items(response, result)

    log.info("  AI 生成成功: %d/%d 个知识点", len(result), len(points))
    return result
