# Amount of lines to display from the top and bottom of the string
from typing import Optional

HEAD = 5
TAIL = 5
MAX_LINE_THRESHOLD = HEAD + TAIL
TRUNCATION_LINE = f"\n(original string is long, truncated to {MAX_LINE_THRESHOLD} lines)"
# The original traceback string, and the placeholder to replace it with, to prevent epsagon from parsing stacktrace
ORIGINAL_TRACEBACK = "Traceback (most recent call last):"
PLACEHOLDER_TRACEBACK = "@@@trace_back@@@"


def truncate_and_clean_traceback(raw_string: Optional[str]) -> str:
    """
    Truncate a large string to 6 lines, and replace the traceback with placeholder
    to prevent epsagon from parsing stacktrace and alert another error in the flow.

    :param raw_string: the string to truncate
    :return: the truncated string
    """
    if not raw_string:
        return ""
    raw_string = raw_string.replace(ORIGINAL_TRACEBACK, PLACEHOLDER_TRACEBACK)

    if raw_string.count("\n") <= MAX_LINE_THRESHOLD:
        return raw_string

    lines = raw_string.splitlines()
    display_lines = lines[:HEAD] + lines[-TAIL:]
    truncated_message = "\n".join(display_lines)
    truncated_message += TRUNCATION_LINE
    return truncated_message
