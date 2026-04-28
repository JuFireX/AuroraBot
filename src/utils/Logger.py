# ------------------------------------------------------------
# @author: Churk
# @status: 完成
# @description: 日志模块
# ------------------------------------------------------------

import functools
import inspect
import logging

from concurrent_log_handler import ConcurrentRotatingFileHandler

from src.config import Config

DEFAULT_LOGFILE = Config.LOG_DIR / "polaris.log"
FORMATTER = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s - %(message)s", "%Y-%m-%d %H:%M:%S"
)


def _create_stream_handler(level=Config.LOG_LEVEL, formatter=FORMATTER):
    sh = logging.StreamHandler()
    sh.setLevel(level)
    sh.setFormatter(formatter)
    return sh


def _create_file_handler(logfile, level=Config.LOG_LEVEL, formatter=FORMATTER):
    # 使用大小轮转日志文件, 每个文件最大100KB, 保留5个备份
    fh = ConcurrentRotatingFileHandler(
        logfile, maxBytes=102400, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(level)
    fh.setFormatter(formatter)
    return fh


class DecoratorFactory:
    """
    一个工厂类, 用于创建日志装饰器, 并将其绑定到指定的日志记录器实例.
    例如, @logger.decorate.info("Executing {func_name}")
    """

    def __init__(self, logger):
        self._logger = logger

    def _create_decorator(self, level, message_template):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Bind arguments to parameter names for rich formatting
                bound_args = inspect.signature(func).bind(*args, **kwargs)
                bound_args.apply_defaults()

                # Create a dictionary of all arguments, including defaults
                all_args = bound_args.arguments

                # Add special and all-encompassing format keys
                format_dict = {
                    **all_args,
                    "func_name": func.__name__,
                    "args": args,
                    "kwargs": kwargs,
                }

                self._logger.log(level, message_template.format(*args, **format_dict))
                return func(*args, **kwargs)

            return wrapper

        return decorator

    def info(self, message_template):
        """创建一个 INFO 级别的日志装饰器, 用于记录函数调用前的信息."""
        return self._create_decorator(logging.INFO, message_template)

    def debug(self, message_template):
        """创建一个 DEBUG 级别的日志装饰器, 用于记录函数调用前的调试信息."""
        return self._create_decorator(logging.DEBUG, message_template)

    def warning(self, message_template):
        """创建一个 WARNING 级别的日志装饰器, 用于记录函数调用前的警告信息."""
        return self._create_decorator(logging.WARNING, message_template)

    def error(self, message_template):
        """创建一个 ERROR 级别的日志装饰器, 用于记录函数调用前的错误信息."""
        return self._create_decorator(logging.ERROR, message_template)


def get_logger(name=None, level=Config.LOG_LEVEL, logfile=None, formatter=FORMATTER):
    """
    返回配置好的日志记录器
    - name: 日志记录器名称 (默认根记录器) .
    - level: 日志级别 (默认从配置文件中获取) .
    - logfile: 日志文件路径. 若为 None 则使用 DEFAULT_LOGFILE .
    - formatter: 日志格式. 若为 None 则使用默认 FORMATTER .
    """
    if name is None:
        # 默认使用根包名, 如果无法获取则使用"Default"
        name = __package__ or "Default"

    logger = logging.getLogger(name)
    if logger.handlers:
        logger.setLevel(level)
        # 若记录器已配置过处理程序, 则直接返回
        if not hasattr(logger, "decorate"):
            setattr(logger, "decorate", DecoratorFactory(logger))
        return logger

    logfile = logfile or DEFAULT_LOGFILE

    logger.setLevel(level)
    logger.propagate = False

    # 配置控制台输出
    logger.addHandler(_create_stream_handler(level, formatter))
    logger.addHandler(_create_file_handler(logfile, level, formatter))

    # 将 DecoratorFactory 实例绑定到记录器, 用于创建日志装饰器
    setattr(logger, "decorate", DecoratorFactory(logger))

    return logger
