try:
    import nonebot

    nonebot.get_driver()
except Exception:
    pass
else:
    from . import main
