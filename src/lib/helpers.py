from datetime import datetime

from botocore.serialize import ISO8601
from botocore.serialize import ISO8601_MICRO
from jit_utils.logger import logger
from jsonpath_ng.ext import parse


def parse_timestamp_iso8601(date: str):
    if "." in date:
        timestamp_format = ISO8601_MICRO
    else:
        timestamp_format = ISO8601
    return datetime.strptime(date, timestamp_format)


def parse_jsonpath(expression: str, data: dict):
    jsonpath_expr = parse(expression)
    match = jsonpath_expr.find(data)
    if not match:
        logger.warning(f"{expression} not found in {data}")
        return None
    if isinstance(match, list):
        return match[0].value
    return match.value
