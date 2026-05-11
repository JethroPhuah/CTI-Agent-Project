"""LLM client wrapper for vLLM (OpenAI-compatible API).

Cross-version safety: langchain-openai keeps adding new request body
fields that strict vLLMs reject. Rather than chase each one, the httpx
hooks here:

* log a compact summary of every chat-completion request (keys only),
* strip a known list of "harmless to drop" fields,
* log the full response body whenever vLLM returns >=400 so we can see
  the exact validation error and add the offending field to the strip
  list (one line in `_sanitize_body`).
"""
import json
import logging
import os
from functools import lru_cache
from typing import Optional

import httpx
from langchain_openai import ChatOpenAI

from .config import get_settings

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Body sanitiser
# ---------------------------------------------------------------------

def _sanitize_body(body: dict) -> bool:
    changed = False
    if body.get("stream") is not True and "stream_options" in body:
        body.pop("stream_options")
        changed = True
    if not body.get("tools") and "parallel_tool_calls" in body:
        body.pop("parallel_tool_calls")
        changed = True
    if body.get("n") == 1:
        body.pop("n", None)
        changed = True
    return changed


def _strip_inplace(request: httpx.Request) -> None:
    if request.method != "POST":
        return
    if not request.url.path.endswith("/chat/completions"):
        return
    try:
        body = json.loads(request.content)
    except Exception:
        return
    log.info("[llm-req] keys=%s msg_count=%d",
             sorted(body.keys()),
             len(body.get("messages") or []))
    if _sanitize_body(body):
        new_content = json.dumps(body).encode("utf-8")
        request._content = new_content
        request.headers["content-length"] = str(len(new_content))
        log.info("[llm-req-stripped] keys=%s", sorted(body.keys()))


def _should_log_response(response: httpx.Response) -> bool:
    return (
        response.request.method == "POST"
        and response.request.url.path.endswith("/chat/completions")
        and response.status_code >= 400
    )


def _emit_response(status: int, text: str) -> None:
    log.error("[llm-resp %s] %s", status, text[:3000])


# Sync flavours
def _sync_req_hook(req: httpx.Request) -> None:
    _strip_inplace(req)


def _sync_resp_hook(resp: httpx.Response) -> None:
    if not _should_log_response(resp):
        return
    try:
        resp.read()
        text = resp.text
    except Exception as e:  # noqa: BLE001
        text = f"<failed to read response body: {e}>"
    _emit_response(resp.status_code, text)


# Async flavours -- httpx awaits these
async def _async_req_hook(req: httpx.Request) -> None:
    _strip_inplace(req)


async def _async_resp_hook(resp: httpx.Response) -> None:
    if not _should_log_response(resp):
        return
    try:
        await resp.aread()
        text = resp.text
    except Exception as e:  # noqa: BLE001
        text = f"<failed to read response body: {e}>"
    _emit_response(resp.status_code, text)


def _make_sync_client() -> httpx.Client:
    return httpx.Client(
        event_hooks={
            "request": [_sync_req_hook],
            "response": [_sync_resp_hook],
        },
        timeout=httpx.Timeout(600, connect=30),
    )


def _make_async_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        event_hooks={
            "request": [_async_req_hook],
            "response": [_async_resp_hook],
        },
        timeout=httpx.Timeout(600, connect=30),
    )


# ---------------------------------------------------------------------
# Cached LLM factory
# ---------------------------------------------------------------------

@lru_cache(maxsize=4)
def get_llm(
    temperature: Optional[float] = None,
    *,
    thinking: bool = False,
    max_tokens: Optional[int] = None,
) -> ChatOpenAI:
    cfg = get_settings()

    kwargs = dict(
        model=cfg.llm_model,
        base_url=cfg.llm_base_url,
        api_key=cfg.llm_api_key or "EMPTY",
        temperature=cfg.llm_temperature if temperature is None else temperature,
        max_retries=2,
        timeout=cfg.llm_timeout,
        stream_usage=False,
        http_client=_make_sync_client(),
        http_async_client=_make_async_client(),
    )

    disable_thinking_env = os.getenv("LLM_DISABLE_THINKING", "").lower() in (
        "1", "true", "yes", "on",
    )
    if disable_thinking_env and not thinking:
        kwargs["extra_body"] = {
            "chat_template_kwargs": {"enable_thinking": False}
        }

    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    return ChatOpenAI(**kwargs)
