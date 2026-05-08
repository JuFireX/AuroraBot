import asyncio
import unittest

from apps.qq import QQApplication
from src.brain.platform.application_host import ApplicationHost


class QQApplicationTest(unittest.TestCase):
    def test_ingest_message_emits_standard_event(self) -> None:
        host = ApplicationHost()

        async def scenario() -> None:
            app = QQApplication(enable_listener=False)
            await host.register(app)
            await app.ingest_message(
                session_id="u1",
                user_id="u1",
                text="你好",
                is_group=False,
                group_id=None,
                bot_id="b1",
            )
            events = host.peek_events()
            self.assertEqual(len(events), 1)
            event = events[0]
            self.assertEqual(event.type, "message.received")
            self.assertEqual(event.source, "im.polaris.qq")
            self.assertEqual(event.payload["text"], "你好")
            await host.stop_all()

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
