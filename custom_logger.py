#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
-------------------------------------------------
  Filename: custom_logger.py
  Desc    :  自定义日志输出格式
  Author  : nfyn
  Created : 2022/6/27
-------------------------------------------------
"""
from sys import stdout

from loguru import logger


def log_formatter(record: dict) -> str:
    """
    格式化每条日志记录 => Formatter for log records
    :param dict record: 日志记录 => Log object containing log metadata & message.
    """
    color_config_dict = {
        'trace': {
            'time': '#70acde',
            'level': '#cfe2f3'
        },
        'info': {
            'time': '#70acde',
            'level': '#9cbfdd'
        },
        'debug': {
            'time': '#70acde',
            'level': '#8598ea'
        },
        'warning': {
            'time': '#70acde',
            'level': '#dcad5a'
        },
        'success': {
            'time': '#70acde',
            'level': '#3dd08d'
        },
        'error': {
            'time': '#70acde',
            'level': '#ae2c2c'
        },
        'default': {
            'time': '#70acde',
            'level': '#b3cfe7'
        }
    }

    level = record["level"].name.lower()
    time_color = color_config_dict.get(level, 'default').get('time')
    level_color = color_config_dict.get(level, 'default').get('level')
    return f"<fg {time_color}>{{time:MM-DD-YYYY HH:mm:ss}}</fg {time_color}> | <fg {level_color}>{{level}}</fg {level_color}>: <light-white>{{message}}</light-white>\n"


def get_logger() -> logger:
    """
    实例化日志类 => Create custom logger.
    """
    logger.remove()
    logger.add(stdout, colorize=True, format=log_formatter)
    return logger


logger = get_logger()