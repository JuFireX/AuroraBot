import asyncio
import unittest

from src.brain.core.capability_registry import (
    CapabilitySpec,
    call,
    clear,
    get_all_schemas,
    register,
    resolve_name,
)


class CapabilityRegistryTest(unittest.TestCase):
    def tearDown(self) -> None:
        clear()

    def test_register_and_call(self) -> None:
        register(
            CapabilitySpec(
                name="demo.echo",
                description="echo",
                parameters_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                handler=lambda text: {"text": text},
            )
        )
        result = asyncio.run(call("demo.echo", {"text": "hello"}))
        self.assertEqual(result, {"text": "hello"})

    def test_llm_schema_uses_safe_alias_and_can_resolve_back(self) -> None:
        register(
            CapabilitySpec(
                name="im.polaris.qq.send_qq_message",
                description="send",
                parameters_schema={"type": "object", "properties": {}, "required": []},
                handler=lambda: {"ok": True},
            )
        )
        schemas = get_all_schemas()
        self.assertEqual(len(schemas), 1)
        public_name = schemas[0]["name"]
        self.assertEqual(public_name, "im_polaris_qq_send_qq_message")
        self.assertEqual(resolve_name(public_name), "im.polaris.qq.send_qq_message")
        result = asyncio.run(call(public_name, {}))
        self.assertEqual(result, {"ok": True})


if __name__ == "__main__":
    unittest.main()
