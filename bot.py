#!/usr/bin/env python3
import nonebot
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11

nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(ONEBOT_V11)
nonebot.load_from_toml("pyproject.toml")

if __name__ == "__main__":
    nonebot.run()
