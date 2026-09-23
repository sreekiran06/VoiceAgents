import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from voice_call_agent.agent.prompt_templates import build_business_prompt
from voice_call_agent.agent.prompts import SYSTEM_PROMPT
from voice_call_agent.agent.tools.lead_tools import register_default_tools
from voice_call_agent.agent.tools.registry import ToolRegistry
from voice_call_agent.core.config import settings
from voice_call_agent.core.context import BusinessContext
from voice_call_agent.models.conversation import CallSession, Message
from voice_call_agent.providers.llm.client import ExpLabsLanguageModel
from voice_call_agent.providers.llm.gemini import GeminiLanguageModel
from voice_call_agent.providers.speech.tts import MockTextToSpeechProvider, TextToSpeechProvider

logger = logging.getLogger(__name__)


def _get_llm():
    """Select the LLM provider based on config."""
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        logger.info("Using Google Gemini LLM (model: gemini-2.0-flash)")
        return GeminiLanguageModel()
    logger.info("Using ExpLabs LLM (model: qwen3.8-27b)")
    return ExpLabsLanguageModel()


class VoiceAgentOrchestrator:
    """Orchestrates conversation turns, tool executions, and audio synthesis for live calls."""

    def __init__(
        self,
        llm: ExpLabsLanguageModel | None = None,
        tts: TextToSpeechProvider | None = None,
        tools: ToolRegistry | None = None,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self.llm = llm or _get_llm()
        self.tts = tts or MockTextToSpeechProvider()
        if tools is not None:
            self.tools = tools
        else:
            self.tools = ToolRegistry()
            register_default_tools(self.tools)
        self.system_prompt = system_prompt

    def _resolve_prompt(self, session: CallSession) -> str:
        """Resolve the system prompt for this call session.

        Priority:
        1. BusinessContext from session (multi-tenant)
        2. Global SYSTEM_PROMPT (single-tenant fallback)
        """
        ctx = session.business_context
        if ctx:
            prompt = build_business_prompt(ctx)
            if prompt:
                return prompt
        return self.system_prompt

    def _get_enabled_tools(self, session: CallSession) -> list[dict[str, Any]]:
        """Get tool schemas filtered by the business context's enabled tools."""
        ctx = session.business_context
        all_tools = self.tools.list_tools()
        if ctx and ctx.enabled_tools:
            enabled = set(ctx.enabled_tools)
            return [t for t in all_tools if t.get("function", {}).get("name") in enabled]
        return all_tools

    def _match_knowledge_fallback(self, ctx: BusinessContext | None, user_text: str) -> str | None:
        """Find the most relevant answer from business knowledge when LLM times out or is offline."""
        if not ctx or not ctx.knowledge:
            return None

        clean_query = user_text.lower().strip()
        words = [w for w in clean_query.replace("?", "").replace(".", "").replace(",", "").split() if len(w) > 2]

        best_match: str | None = None
        max_score = 0

        for entry in ctx.knowledge:
            q = entry.get("question", "").lower()
            ans = entry.get("answer", "")
            cat = entry.get("category", "").lower()

            # Check direct question substring
            if q and (q in clean_query or clean_query in q):
                return ans

            # Keyword score matching
            score = 0
            for w in words:
                if w in q:
                    score += 3
                elif w in ans.lower():
                    score += 1
                if cat and w in cat:
                    score += 2

            if score > max_score and score >= 2:
                max_score = score
                # If answer contains dialog lines (e.g. 'ఏజెంట్: ...' or 'A: ...'), extract the agent response
                if "ఏజెంట్:" in ans:
                    matching_agent_line = None
                    for line in ans.splitlines():
                        if "ఏజెంట్:" in line:
                            matching_agent_line = line.replace("ఏజెంట్:", "").strip()
                            break
                    best_match = matching_agent_line or ans
                elif "A:" in ans:
                    matching_a_line = None
                    for line in ans.splitlines():
                        if "A:" in line:
                            matching_a_line = line.replace("A:", "").strip()
                            break
                    best_match = matching_a_line or ans
                else:
                    best_match = ans

        return best_match

    async def handle_turn(
        self,
        session: CallSession,
        user_transcript: str,
    ) -> tuple[str, bytes, list[dict[str, Any]]]:
        """Process a caller turn: LLM completion, tool execution, and TTS synthesis.

        Returns:
            (assistant_text, audio_mulaw_bytes, executed_tools)
        """
        # 1. Append user message to call session
        session.messages.append(Message(role="user", content=user_transcript))

        # 2. Build messages payload for LLM
        prompt = self._resolve_prompt(session)
        llm_messages: list[dict[str, Any]] = [
            {"role": "system", "content": prompt}
        ]
        for msg in session.messages:
            llm_messages.append({"role": msg.role, "content": msg.content})

        tools_schema = self._get_enabled_tools(session)

        # 3. Call LLM
        executed_tools: list[dict[str, Any]] = []
        assistant_reply_text = ""

        try:
            response_message = await self.llm.generate_response(llm_messages, tools=tools_schema)
            tool_calls = response_message.get("tool_calls", [])

            # Handle any tool calls emitted by LLM
            if tool_calls:
                for tool_call in tool_calls:
                    fn = tool_call.get("function", {})
                    fn_name = fn.get("name")
                    raw_args = fn.get("arguments", "{}")
                    fn_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    logger.info("Executing tool: %s with args: %s", fn_name, fn_args)

                    tool_exec_result = await self.tools.execute(fn_name, fn_args)
                    executed_tools.append({
                        "tool": fn_name,
                        "args": fn_args,
                        "result": tool_exec_result,
                    })

                    # Store qualified lead or booking in session metadata
                    if fn_name == "qualify_lead":
                        session.metadata["lead"] = fn_args
                    elif fn_name == "book_appointment":
                        session.metadata["appointment"] = fn_args
                    elif fn_name == "transfer_to_human":
                        session.metadata["transfer"] = fn_args

            assistant_reply_text = response_message.get("content") or ""

            # If LLM only issued tool calls without text, provide a natural spoken confirmation
            if not assistant_reply_text.strip() and executed_tools:
                first_tool = executed_tools[0]
                if first_tool["tool"] == "qualify_lead":
                    assistant_reply_text = "I have noted your requirements. Is there anything else you would like to know?"
                elif first_tool["tool"] == "book_appointment":
                    assistant_reply_text = "Your appointment has been successfully scheduled. Thank you!"
                elif first_tool["tool"] == "transfer_to_human":
                    assistant_reply_text = "Please hold on while I transfer your call to our executive."
                else:
                    assistant_reply_text = "Thank you, I have recorded your request."

        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM call encountered error (%s). Using business knowledge base matching.", exc)
            ctx = session.business_context
            matched_reply = self._match_knowledge_fallback(ctx, user_transcript)
            if matched_reply:
                assistant_reply_text = matched_reply
            elif ctx and ctx.fallback_message:
                assistant_reply_text = ctx.fallback_message
            else:
                assistant_reply_text = "Thank you for reaching out. How can I assist you with your enquiry today?"

        # 4. Record assistant message in conversation history
        session.messages.append(Message(role="assistant", content=assistant_reply_text))

        # 5. Synthesize speech into 8kHz mu-law audio
        synthesis = await self.tts.synthesize(assistant_reply_text)

        return assistant_reply_text, synthesis.audio_mulaw_bytes, executed_tools

    @staticmethod
    async def chunk_mulaw_stream(
        audio_mulaw_bytes: bytes,
        chunk_size: int = 160,
    ) -> AsyncIterator[bytes]:
        """Yield 20ms chunks (160 bytes of 8kHz mu-law) for steady telephony streaming."""
        for i in range(0, len(audio_mulaw_bytes), chunk_size):
            yield audio_mulaw_bytes[i : i + chunk_size]
