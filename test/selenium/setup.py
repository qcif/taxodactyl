from pathlib import Path
from types import SimpleNamespace
from typing import Generator

import pandas as pd
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


@pytest.fixture
def driver() -> Generator[webdriver.Chrome, None, None]:
    options = Options()
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )

    yield driver
    driver.quit()


def csv_to_namespace(csv_path: Path) -> SimpleNamespace:
    df: pd.DataFrame = pd.read_csv(csv_path)

    reports: list[str] = [c for c in df.columns if c.endswith(".html")]
    root = SimpleNamespace()

    for component in df["Component"].unique():
        comp_ns = SimpleNamespace()
        comp_df = df[df["Component"] == component]

        for report in reports:
            report_ns = SimpleNamespace()

            for _, row in comp_df.iterrows():
                val = row[report]

                if pd.isna(val):
                    val = None
                elif row["Type"] == "list":
                    val = str(val).split("|")
                elif row["Type"] == "int":
                    val = int(val)

                setattr(report_ns, row["Assertion ID"], val)

            setattr(comp_ns, report, report_ns)

        setattr(root, component, comp_ns)

    return root
