from typing import Optional
from typing import TypeVar

from jit_utils.logger import logger
from pydantic import ValidationError

T = TypeVar("T")


def try_parse_dict(dictionary: dict, model: T) -> Optional[T]:
    """
    This function will try parse a dict to a pydantic model T.
    Use this is order to be able to not raise a ValidationError.

    Example:
        parsed = try_parse_dict(dictionary={"a": 1}, model=SomePydanticModel)
    """
    try:
        return model(**dictionary)
    except ValidationError:
        logger.info(f"Could not parse as {model}")
        return None
