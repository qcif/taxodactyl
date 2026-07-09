from pathlib import Path

import pytest

from lib.driver import make_driver


DEFAULT_REPORTS_DIR = "reports"


def pytest_addoption(parser):
    parser.addoption(
        "--reports-dir",
        action="store",
        default=DEFAULT_REPORTS_DIR,
        help=(
            "Directory containing HTML reports to test against "
            f"(default: {DEFAULT_REPORTS_DIR}). Reports are matched to "
            "expected/*.yaml fixtures by sample_id, so timestamps in "
            "the report filename may differ."
        ),
    )


@pytest.fixture(scope="session")
def reports_dir(request):
    return Path(request.config.getoption("--reports-dir"))


@pytest.fixture
def driver():
    driver = make_driver()
    yield driver
    driver.quit()
