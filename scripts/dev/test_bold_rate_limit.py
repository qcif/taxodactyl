"""Test the BOLD API until rate limit is reached.

OUTCOME - tests strongly suggest a rate limit of 250 requests per hour or day.

"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT_DIR / 'scripts'))

from src.bold.stats import fetch_bold_records_count  # noqa: E402
from src.utils.config import Config  # noqa: E402

config = Config()
config.configure(output_dir=ROOT_DIR / 'output/bold/api_test')

BOLD_TAXA_JSON = ROOT_DIR / 'output/bold/bold_taxonomy.json'
COMPLETED_TASKS = ROOT_DIR / 'output/bold/completed_tasks.json'

bold_taxa = list(
    json.loads(
        BOLD_TAXA_JSON.read_text(encoding='utf-8')
    ).keys()
)

error = False
t0 = time.time()
tasks = [
    (fetch_bold_records_count, taxon)
    for taxon in bold_taxa
]
completed = []

while True:
    print(f'Threading batch of {len(tasks)} tasks...')
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {
            executor.submit(func, taxon): taxon
            for func, taxon in tasks
        }
        for future in as_completed(futures):
            taxon = futures[future]
            count = future.result()
            if count is None:
                error = True
                break
            completed.append((time.time() - t0, count))
    if error:
        print('Error occurred while fetching BOLD records. Exiting.')
        break
    print(f"Completed task batch ({len(completed)} total).")
    if len(completed) >= 150:
        print('Reached 150 completed tasks, stopping.')
        break

elapsed = time.time() - t0
print(f'Fetched {len(completed)} taxa in {elapsed:.2f} seconds.')

COMPLETED_TASKS.write_text(
    json.dumps(
        completed,
        indent=2,
        ensure_ascii=False
    ),
    encoding='utf-8',
)
print(f'Completed tasks written to {COMPLETED_TASKS}.')
