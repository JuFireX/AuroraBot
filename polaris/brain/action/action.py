from polaris.services.RestService import *
from polaris.services.TimeService import *
from polaris.services.QQMsgService import *
from polaris.utils.Logger import get_logger


logger = get_logger("AgentActions")


# 服务路由表
ACTION_ROUTER = {
    "reply_qq": reply_qq,
    "check_time": check_time,
    "sleep": sleep,
    "rest": rest,
    "idle": idle,
}
