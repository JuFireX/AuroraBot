from __future__ import annotations

import asyncio
import unittest
from typing import List, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import litellm.exceptions

from src.brain.ai.llm_gate import LLMGateError, llm_chat
from src.config import Config

_MESSAGES: List[Dict[str, str]] = [
    {"role": "system", "content": "\u4f60\u662f\u4e00\u4e2a\u52a9\u624b\u3002"},
    {"role": "user", "content": "\u4f60\u597d"},
]


def _make_mock_response(content: str | None) -> MagicMock:
    response = MagicMock()
    choice = MagicMock()
    message = MagicMock()
    message.content = content
    choice.message = message
    response.choices = [choice]
    return response


class LLMGateNormalFlowTest(unittest.TestCase):

    def test_returns_model_text_content(self) -> None:
        mock_resp = _make_mock_response(
            "\u4f60\u597d\uff0c\u6211\u662f AuroraBot\u3002"
        )

        async def scenario() -> None:
            with patch(
                "src.brain.ai.llm_gate.acompletion",
                new=AsyncMock(return_value=mock_resp),
            ):
                result = await llm_chat(_MESSAGES, max_tokens=256)
            self.assertEqual(result, "\u4f60\u597d\uff0c\u6211\u662f AuroraBot\u3002")

        asyncio.run(scenario())

    def test_extracts_content_when_none_returns_empty_string(self) -> None:
        mock_resp = _make_mock_response(None)

        async def scenario() -> None:
            with patch(
                "src.brain.ai.llm_gate.acompletion",
                new=AsyncMock(return_value=mock_resp),
            ):
                result = await llm_chat(_MESSAGES)
            self.assertEqual(result, "")

        asyncio.run(scenario())

    def test_passes_kwargs_to_acompletion(self) -> None:
        mock_resp = _make_mock_response("ok")

        async def scenario() -> None:
            with patch(
                "src.brain.ai.llm_gate.acompletion",
                new=AsyncMock(return_value=mock_resp),
            ) as mock_acompletion:
                await llm_chat(
                    _MESSAGES,
                    max_tokens=128,
                    temperature=0.7,
                    top_p=0.9,
                )
            call_kwargs = mock_acompletion.call_args.kwargs
            self.assertEqual(call_kwargs["temperature"], 0.7)
            self.assertEqual(call_kwargs["top_p"], 0.9)
            self.assertEqual(call_kwargs["max_tokens"], 128)

        asyncio.run(scenario())


class LLMGateConfigTest(unittest.TestCase):

    def test_raises_value_error_when_model_is_empty(self) -> None:
        original = Config.LITELLM_MODEL
        Config.LITELLM_MODEL = ""

        async def scenario() -> None:
            with self.assertRaises(ValueError) as ctx:
                await llm_chat(_MESSAGES)
            self.assertIn("LITELLM_MODEL", str(ctx.exception))

        try:
            asyncio.run(scenario())
        finally:
            Config.LITELLM_MODEL = original

    def test_raises_value_error_when_model_is_whitespace(self) -> None:
        original = Config.LITELLM_MODEL
        Config.LITELLM_MODEL = "   "

        async def scenario() -> None:
            with self.assertRaises(ValueError):
                await llm_chat(_MESSAGES)

        try:
            asyncio.run(scenario())
        finally:
            Config.LITELLM_MODEL = original


class LLMGateModelBlockedTest(unittest.TestCase):

    def test_raises_permission_error_when_model_in_kwargs(self) -> None:
        async def scenario() -> None:
            with self.assertRaises(PermissionError) as ctx:
                await llm_chat(_MESSAGES, model="gpt-4o")
            self.assertIn("model", str(ctx.exception).lower())

        asyncio.run(scenario())


class LLMGateExceptionConversionTest(unittest.TestCase):

    def _assert_raises_llm_gate(
        self,
        exc_to_raise: Exception,
        *,
        expected_retryable: bool,
    ) -> None:
        async def scenario() -> None:
            with patch(
                "src.brain.ai.llm_gate.acompletion",
                new=AsyncMock(side_effect=exc_to_raise),
            ):
                with self.assertRaises(LLMGateError) as ctx:
                    await llm_chat(_MESSAGES)
            self.assertEqual(
                ctx.exception.retryable,
                expected_retryable,
                f"retryable \u5e94\u4e3a {expected_retryable}\uff0c\u5b9e\u9645 {ctx.exception.retryable}",
            )

        asyncio.run(scenario())

    def test_timeout_is_retryable(self) -> None:
        exc = litellm.exceptions.Timeout(
            message="Request timed out",
            model="mock-model",
            llm_provider="mock-provider",
        )
        self._assert_raises_llm_gate(exc, expected_retryable=True)

    def test_rate_limit_is_retryable(self) -> None:
        exc = litellm.exceptions.RateLimitError(
            message="Rate limit exceeded",
            model="mock-model",
            llm_provider="mock-provider",
        )
        self._assert_raises_llm_gate(exc, expected_retryable=True)

    def test_api_connection_error_is_retryable(self) -> None:
        exc = litellm.exceptions.APIConnectionError(
            message="Connection failed",
            llm_provider="mock-provider",
            model="mock-model",
        )
        self._assert_raises_llm_gate(exc, expected_retryable=True)

    def test_service_unavailable_is_retryable(self) -> None:
        exc = litellm.exceptions.ServiceUnavailableError(
            message="Service unavailable",
            llm_provider="mock-provider",
            model="mock-model",
        )
        self._assert_raises_llm_gate(exc, expected_retryable=True)

    def test_internal_server_error_is_retryable(self) -> None:
        exc = litellm.exceptions.InternalServerError(
            message="Internal error",
            llm_provider="mock-provider",
            model="mock-model",
        )
        self._assert_raises_llm_gate(exc, expected_retryable=True)

    def test_api_error_is_retryable(self) -> None:
        exc = litellm.exceptions.APIError(
            status_code=500,
            message="Generic API error",
            llm_provider="mock-provider",
            model="mock-model",
        )
        self._assert_raises_llm_gate(exc, expected_retryable=True)

    def test_authentication_error_is_not_retryable(self) -> None:
        exc = litellm.exceptions.AuthenticationError(
            message="Invalid API key",
            llm_provider="mock-provider",
            model="mock-model",
        )
        self._assert_raises_llm_gate(exc, expected_retryable=False)

    def test_bad_request_error_is_not_retryable(self) -> None:
        exc = litellm.exceptions.BadRequestError(
            message="Bad request",
            model="mock-model",
            llm_provider="mock-provider",
        )
        self._assert_raises_llm_gate(exc, expected_retryable=False)

    def test_unsupported_params_error_is_not_retryable(self) -> None:
        exc = litellm.exceptions.UnsupportedParamsError(
            message="Unsupported param",
            llm_provider="mock-provider",
            model="mock-model",
        )
        self._assert_raises_llm_gate(exc, expected_retryable=False)

    def test_unexpected_exception_is_not_retryable(self) -> None:
        self._assert_raises_llm_gate(
            RuntimeError("some unexpected crash"),
            expected_retryable=False,
        )

    def test_exception_chaining_preserves_cause(self) -> None:
        original = litellm.exceptions.Timeout(
            message="timed out",
            model="mock-model",
            llm_provider="mock-provider",
        )

        async def scenario() -> None:
            with patch(
                "src.brain.ai.llm_gate.acompletion",
                new=AsyncMock(side_effect=original),
            ):
                with self.assertRaises(LLMGateError) as ctx:
                    await llm_chat(_MESSAGES)
            self.assertIs(ctx.exception.__cause__, original)

        asyncio.run(scenario())


class LLMGateErrorAttributesTest(unittest.TestCase):

    def test_retryable_defaults_to_false(self) -> None:
        error = LLMGateError("test")
        self.assertFalse(error.retryable)

    def test_retryable_explicit_true(self) -> None:
        error = LLMGateError("test", retryable=True)
        self.assertTrue(error.retryable)

    def test_message_preserved(self) -> None:
        error = LLMGateError("something went wrong", retryable=True)
        self.assertEqual(str(error), "something went wrong")


if __name__ == "__main__":
    unittest.main()
