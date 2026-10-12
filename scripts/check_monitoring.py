"""Wait for the local Prometheus instance to scrape the bank successfully."""

import time
import requests

for attempt in range(25):
    response = requests.get("http://127.0.0.1:9090/api/v1/targets", timeout=5)
    response.raise_for_status()
    targets = response.json()["data"]["activeTargets"]
    if any(
        t["labels"].get("job") == "porquinho-bank" and t["health"] == "up"
        for t in targets
    ):
        print("Prometheus collected authenticated bank metrics successfully.")
        break
    time.sleep(1)
else:
    raise SystemExit("Prometheus did not collect bank metrics: " + str(targets))
