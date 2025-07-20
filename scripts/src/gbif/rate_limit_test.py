"""Send some requests to GBIF to estimate the rate limit."""

import pygbif
from time import time
from concurrent.futures import ThreadPoolExecutor, as_completed

TOTAL_REQUESTS = 20
MAX_THREADS = 20


def make_request():
    # pygbif.occurrences.search(
    #     taxonKey=3329049,
    #     country='CA',
    #     facet="speciesKey",
    #     facetLimit=500,
    #     limit=1,
    # )
    # pygbif.species.name_suggest(
    #     q='Homo sapiens',
    #     rank='species',
    #     limit=20,
    # )
    pygbif.species.name_lookup(
        rank='species',
        higherTaxonKey='2436435',
        limit=500,
    )


start_time = time()

# Create a ThreadPoolExecutor with a maximum of 50 threads
with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
    # Submit all requests to the thread pool
    futures = [executor.submit(make_request) for _ in range(TOTAL_REQUESTS)]

    # Control request rate and process results as they complete
    for i, future in enumerate(as_completed(futures)):
        try:
            future.result()  # Wait for the request to complete
            print(f"Search {i} completed")
        except Exception as e:
            print(f"Request {i + 1} failed with exception: {e}")

# End timing
end_time = time()
print(f"Completed {TOTAL_REQUESTS} requests in {end_time - start_time:.2f}"
      " seconds.")
