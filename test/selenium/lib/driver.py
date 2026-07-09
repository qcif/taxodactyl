"""Chrome WebDriver factory shared by pytest and testkit CLI."""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


def make_driver(headless: bool = False):
    options = Options()
    options.add_argument("--window-size=1920,1080")
    if headless:
        options.add_argument("--headless=new")
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )
