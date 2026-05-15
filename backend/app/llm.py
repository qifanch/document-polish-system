from __future__ import annotations

from typing import Any

import httpx

from .config import DeepSeekSettings, get_deepseek_settings


class LLMError(RuntimeError):
    retryable = False


class LLMTemporaryError(LLMError):
    retryable = True


class LLMPermanentError(LLMError):
    retryable = False


DEEPSEEK_DISABLED_THINKING = {"type": "disabled"}
DEEPSEEK_ENABLED_THINKING = {"type": "enabled"}


def mask_llm_error(error: Exception) -> str:
    message = str(error)
    settings = get_deepseek_settings()
    if settings.api_key:
        message = message.replace(settings.api_key, "******")
    return message


def build_chat_completions_url(settings: DeepSeekSettings) -> str:
    return f"{settings.base_url.rstrip('/')}/chat/completions"


def normalize_chat_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                if item.strip():
                    text_parts.append(item.strip())
                continue
            if not isinstance(item, dict):
                continue
            if str(item.get("type") or "").strip() != "text":
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                text_parts.append(text.strip())
        return "\n".join(text_parts).strip()
    return ""


def raise_for_empty_or_non_text_response(finish_reason: str, message: Any) -> None:
    if finish_reason == "insufficient_system_resource":
        raise LLMTemporaryError("DeepSeek temporary resource shortage (finish_reason=insufficient_system_resource).")
    if finish_reason == "content_filter":
        raise LLMPermanentError("DeepSeek rejected the request due to content filtering (finish_reason=content_filter).")
    if finish_reason == "length":
        raise LLMPermanentError("DeepSeek response was truncated before returning usable content (finish_reason=length).")

    if isinstance(message, dict) and message.get("tool_calls"):
        raise LLMPermanentError("DeepSeek returned tool calls instead of plain text content.")

    if finish_reason == "tool_calls":
        raise LLMPermanentError("DeepSeek returned tool calls instead of plain text content.")
    if finish_reason and finish_reason != "stop":
        raise LLMTemporaryError(f"DeepSeek returned no usable text (finish_reason={finish_reason}).")
    raise LLMTemporaryError("DeepSeek returned an empty text response.")


def is_deepseek_reasoning_model(model: str) -> bool:
    return "reasoner" in str(model or "").lower()


def ensure_non_reasoning_model(settings: DeepSeekSettings) -> None:
    if is_deepseek_reasoning_model(settings.model):
        raise LLMPermanentError("DEEPSEEK_MODEL is configured as a reasoning model; disable thinking by using a non-reasoning model.")


def build_deepseek_chat_payload(
    settings: DeepSeekSettings,
    messages: list[dict[str, str]],
    *,
    max_tokens: int,
    temperature: float,
    thinking_type: str = "disabled",
) -> dict[str, Any]:
    thinking = DEEPSEEK_ENABLED_THINKING if thinking_type == "enabled" else DEEPSEEK_DISABLED_THINKING
    if thinking["type"] == "disabled":
        ensure_non_reasoning_model(settings)
    return {
        "model": settings.model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
        "thinking": thinking,
    }


def get_deepseek_config_status() -> dict[str, bool]:
    settings = get_deepseek_settings()
    return {
        "configured": bool(settings.api_key and settings.model),
    }


def check_deepseek_connection() -> dict[str, Any]:
    settings = get_deepseek_settings()
    status: dict[str, Any] = {
        "configured": bool(settings.api_key and settings.model),
        "connected": False,
        "baseUrl": settings.base_url,
        "model": settings.model,
    }

    if not settings.api_key:
        status["error"] = "DEEPSEEK_API_KEY is not configured."
        return status
    if not settings.model:
        status["error"] = "DEEPSEEK_MODEL is not configured."
        return status

    try:
        payload = build_deepseek_chat_payload(
            settings,
            [{"role": "user", "content": "ping"}],
            max_tokens=1,
            temperature=0,
        )
    except LLMPermanentError as exc:
        status["error"] = str(exc)
        return status

    try:
        response = httpx.post(
            build_chat_completions_url(settings),
            headers={
                "Authorization": f"Bearer {settings.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=8,
        )
        if response.status_code >= 400:
            status["error"] = f"DeepSeek check failed with HTTP {response.status_code}."
            return status

        response.json()
    except Exception as exc:
        status["error"] = mask_llm_error(exc)
        return status

    status["connected"] = True
    return status


def run_deepseek_chat_completion(
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 1800,
    temperature: float = 0.2,
    thinking_type: str = "disabled",
) -> dict[str, Any]:
    settings = get_deepseek_settings()
    if not settings.api_key:
        raise LLMPermanentError("DEEPSEEK_API_KEY is not configured.")
    if not settings.model:
        raise LLMPermanentError("DEEPSEEK_MODEL is not configured.")

    payload = build_deepseek_chat_payload(
        settings,
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
        thinking_type=thinking_type,
    )

    try:
        response = httpx.post(
            build_chat_completions_url(settings),
            headers={
                "Authorization": f"Bearer {settings.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=45,
        )
        if response.status_code >= 400:
            message = f"DeepSeek request failed with HTTP {response.status_code}."
            if response.status_code == 429 or response.status_code >= 500:
                raise LLMTemporaryError(message)
            raise LLMPermanentError(message)
        data = response.json()
    except (LLMTemporaryError, LLMPermanentError):
        raise
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise LLMTemporaryError(mask_llm_error(exc)) from exc
    except Exception as exc:
        raise LLMTemporaryError(mask_llm_error(exc)) from exc

    choices = data.get("choices") if isinstance(data, dict) else None
    if not choices:
        raise LLMTemporaryError("DeepSeek response does not contain choices.")

    first_choice = choices[0] if isinstance(choices[0], dict) else {}
    finish_reason = str(first_choice.get("finish_reason") or "").strip()
    message = first_choice.get("message") if isinstance(first_choice, dict) else None
    content = normalize_chat_message_content(message.get("content") if isinstance(message, dict) else "")
    if not content:
        raise_for_empty_or_non_text_response(finish_reason, message)

    return {
        "content": content,
        "model": str(data.get("model") or settings.model),
        "finishReason": finish_reason,
    }
