import pytest

from src.lib.cores.utils.truncate import HEAD
from src.lib.cores.utils.truncate import ORIGINAL_TRACEBACK
from src.lib.cores.utils.truncate import PLACEHOLDER_TRACEBACK
from src.lib.cores.utils.truncate import TAIL
from src.lib.cores.utils.truncate import truncate_and_clean_traceback
from src.lib.cores.utils.truncate import TRUNCATION_LINE


def generate_lines(num_lines):
    return "\n".join(f"line{i}" for i in range(1, num_lines + 1))


first_lines = generate_lines(HEAD)
last_lines = '\n'.join(generate_lines(12).split('\n')[-TAIL:])

test_cases = [
    (generate_lines(5), generate_lines(5), "small string should not truncate"),
    (generate_lines(10), f"{generate_lines(10)}", "equal to max lines string should not truncate"),
    (generate_lines(12), f"{first_lines}\n{last_lines}{TRUNCATION_LINE}",
     "large string should truncate"),
    (f"{ORIGINAL_TRACEBACK}\n{generate_lines(6)}", f"{PLACEHOLDER_TRACEBACK}\n{generate_lines(6)}",
     "str with stacktrace should replace traceback"),
]


@pytest.mark.parametrize("raw_string, expected_result, _", test_cases, ids=[name for _, _, name in test_cases])
def test_truncate_and_clean_traceback(raw_string, expected_result, _):
    assert truncate_and_clean_traceback(raw_string) == expected_result
