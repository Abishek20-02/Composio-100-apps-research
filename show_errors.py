"""Quick helper: print just the _error fields from research_raw.json, plain and simple."""
import json

with open("output/research_raw.json") as f:
    data = json.load(f)

for entry in data:
    if "_error" in entry:
        print(f"{entry.get('_app_name', '?')}: {entry['_error']}")
        print("---")
