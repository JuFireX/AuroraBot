import asyncio
import unittest

from apps.alarm import AlarmApplication
from apps.diary import DiaryApplication
from apps.qq import QQApplication
from src.brain.platform.application_host import ApplicationHost


class ApplicationHostTest(unittest.TestCase):
    def test_registers_commands_from_manifests(self) -> None:
        host = ApplicationHost()

        async def scenario() -> None:
            await host.register(DiaryApplication())
            await host.register(AlarmApplication())
            await host.register(QQApplication(enable_listener=False))
            commands = host.list_commands()
            self.assertIn("im.polaris.diary.write_diary", commands)
            self.assertIn("im.polaris.alarm.set_alarm", commands)
            self.assertIn("im.polaris.qq.send_qq_message", commands)
            await host.stop_all()

        asyncio.run(scenario())

    def test_alarm_tick_emits_event(self) -> None:
        host = ApplicationHost()

        async def scenario() -> None:
            await host.register(AlarmApplication())
            await host.invoke_command(
                "im.polaris.alarm.set_alarm",
                message="test alarm",
                interval_seconds=0,
            )
            await host.tick()
            events = host.peek_events()
            self.assertTrue(events)
            self.assertEqual(events[-1].type, "alarm_reminder")
            self.assertEqual(events[-1].source, "im.polaris.alarm")
            await host.stop_all()

        asyncio.run(scenario())

    def test_diary_write_emits_event(self) -> None:
        host = ApplicationHost()

        async def scenario() -> None:
            await host.register(DiaryApplication())
            result = await host.invoke_command(
                "im.polaris.diary.write_diary",
                date="2026-05-08",
                summary="测试记录",
            )
            self.assertTrue(result["saved"])
            events = host.peek_events()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].type, "diary.written")
            await host.stop_all()

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
