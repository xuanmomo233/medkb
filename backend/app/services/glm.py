"""智谱 GLM 调用封装（多模型依次回退）。供 AI 解析、AI 陪学共用。"""
import httpx

from app.core.config import get_settings

GLM_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


async def glm_call(
    messages: list[dict],
    *,
    tools: list[dict] | None = None,
    models: list[str] | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    think: str | None = None,
    timeout: float = 60,
) -> dict | None:
    """单次调用，按 models 顺序回退；返回 message dict（含 content / tool_calls），全部失败返回 None。"""
    st = get_settings()
    key = st.glm_api_key.get_secret_value()
    if not key:
        return None
    async with httpx.AsyncClient(timeout=timeout) as client:
        for model in models or st.glm_model_list:
            body: dict = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
            if tools:
                body["tools"] = tools
            if think:
                body["thinking"] = {"type": think}
            try:
                r = await client.post(GLM_URL, json=body, headers={"Authorization": f"Bearer {key}"})
                r.raise_for_status()
                msg = (r.json().get("choices") or [{}])[0].get("message") or {}
                if msg.get("content") or msg.get("tool_calls"):
                    return msg
            except (httpx.HTTPError, ValueError):
                continue
    return None
