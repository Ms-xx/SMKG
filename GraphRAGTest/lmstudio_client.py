"""
LM Studio LLM 客户端
封装与 LM Studio 本地推理服务器的交互
支持: 模型列表查询 / 模型加载 / Chat Completion / Direct Generation
"""
from typing import Any, Optional
import httpx
from config import settings
from loguru import logger


class LMStudioClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.LMSTUDIO_BASE_URL).rstrip("/")
        self._current_model: Optional[str] = None

    # ─── 模型管理 ───────────────────────────────────────

    def list_models(self) -> dict[str, Any]:
        """GET /api/v0/models — 列出 LM Studio 中已下载/已加载的模型（含 state 状态）"""
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{self.base_url}/api/v0/models")
            resp.raise_for_status()
            return resp.json()

    def get_loaded_model(self) -> dict[str, Any]:
        """获取当前加载的模型信息"""
        models = self.list_models()
        # LM Studio 返回 { "data": [{ "id": "...", "state": "loaded", ... }] }
        for model in models.get("data", []):
            if model.get("state") == "loaded":
                self._current_model = model["id"]
                return model
        return {}

    def load_model(self, model_id: str | None = None) -> dict[str, Any]:
        """
        POST /api/v1/models/load — 让 LM Studio 预加载模型到显存/内存
        模型 ID 示例: "qwen/qwen3-4b-2507"
        """
        target = model_id or settings.LMSTUDIO_MODEL
        payload: dict[str, Any] = {"model": target}
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(f"{self.base_url}/api/v1/models/load", json=payload)
            resp.raise_for_status()
            result = resp.json()
            self._current_model = target
            logger.info(f"Model loaded: {target}")
            return result

    def unload_model(self, model_id: str | None = None) -> dict[str, Any]:
        """POST /api/v1/models/unload — 卸载模型"""
        target = model_id or self._current_model
        if not target:
            return {"message": "No model currently loaded"}
        payload: dict[str, Any] = {"model": target}
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{self.base_url}/api/v1/models/unload", json=payload)
            resp.raise_for_status()
            self._current_model = None
            return resp.json()

    # ─── LLM 生成 ───────────────────────────────────────

    def chat_complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stop: list[str] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        POST /api/v1/chat — Chat Completion 接口
        LM Studio 格式: input 为数组 [{"type": "text", "content": "..."}]
        """
        model_name = model or self._current_model or settings.LMSTUDIO_MODEL

        # 合并额外参数
        extra_params = {}
        for k, v in kwargs.items():
            if k in ("top_p", "top_k", "frequency_penalty", "presence_penalty", "repeat_penalty"):
                extra_params[k] = v

        # LM Studio 格式: input 必须是数组
        content = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
        payload = {
            "model": model_name,
            "input": [
                {
                    "type": "text",
                    "content": content
                }
            ],
            "temperature": temperature,
            "stream": False,
        }
        if stop:
            payload["stop"] = stop
        payload.update(extra_params)

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(f"{self.base_url}/api/v1/chat", json=payload)
            resp.raise_for_status()
            return resp.json()

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system_prompt: str | None = None,
        stop: list[str] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        POST /api/v1/chat — 直接文本补全
        (将 prompt 包装为单轮 user 消息)
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat_complete(messages, model=model, temperature=temperature, max_tokens=max_tokens, stop=stop, **kwargs)

    def extract_content(self, response: dict[str, Any]) -> str:
        """从 LM Studio 响应中提取文本内容"""
        try:
            # 方式1: output 数组 (LM Studio 格式)
            if "output" in response and isinstance(response["output"], list):
                for item in response["output"]:
                    if isinstance(item, dict) and item.get("type") == "message":
                        return item.get("content", "")

            # 方式2: content 字段
            if "content" in response:
                return str(response["content"])

            # 方式3: response 字段
            if "response" in response:
                return str(response["response"])

            # 方式4: text 字段
            if "text" in response:
                return str(response["text"])

            # 方式5: OpenAI 兼容格式
            choices = response.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                return msg.get("content", "")

            # 如果都没有，返回整个响应字符串
            return str(response)
        except Exception:
            return str(response)

    # ─── 便捷方法 ───────────────────────────────────────

    def ask(
        self,
        question: str,
        system_prompt: str = "你是一个有帮助的AI助手。",
        **kwargs,
    ) -> str:
        """简单的问答接口"""
        response = self.generate(
            prompt=question,
            system_prompt=system_prompt,
            **kwargs,
        )
        return self.extract_content(response)

    def ask_with_context(
        self,
        question: str,
        context: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        """基于上下文的问答"""
        default_system = (
            "你是一个基于知识图谱的问答助手。"
            "根据提供的上下文信息, 准确、简洁地回答用户问题。"
            "如果上下文中没有足够信息, 请如实说明。"
        )
        prompt = (
            f"=== 知识图谱上下文 ===\n{context}\n\n"
            f"=== 用户问题 ===\n{question}\n\n"
            "=== 回答 ==="
        )
        return self.ask(prompt, system_prompt=system_prompt or default_system, **kwargs)


# 全局单例
llm_client = LMStudioClient()
