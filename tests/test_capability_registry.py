import asyncio
import unittest

from src.brain.core.capability_registry import CapabilitySpec, call, clear, register


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


if __name__ == "__main__":
    unittest.main()
