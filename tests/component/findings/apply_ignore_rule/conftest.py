import datetime

import pytest
from freezegun import freeze_time

TESTS_TIME = datetime.date.fromisoformat("2022-01-14")


@pytest.fixture(scope="session", autouse=True)
def freeze_time_for_tests():
    freezer = freeze_time(TESTS_TIME)
    freezer.start()
    yield
    freezer.stop()
