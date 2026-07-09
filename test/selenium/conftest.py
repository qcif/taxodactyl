import pytest

from lib.driver import make_driver


@pytest.fixture
def driver():
    driver = make_driver()
    yield driver
    driver.quit()
