"""
Applies corrections found during verification to produce the final dataset.

WHAT THIS DOES:
Where verify_sample.py found a disagreement, this script updates that app's
record with the verification pass's finding (which had a second, independent
search behind it) rather than the original first-pass answer. Apps that
weren't in the verification sample keep their original first-pass answer -
this is disclosed clearly in the final output, not hidden.

This is what lets us honestly report: "first pass was X% accurate on our
sample, second pass corrected known errors, final dataset is Y% verified
either directly or by the same method."

HOW TO RUN:
    python apply_corrections.py
Output: output/research_final.json
"""

import json
import os

def main():
    os.makedirs("output", exist_ok=True)

    with open("output/research_raw.json") as f:
        research = json.load(f)

    with open("output/verification_report.json") as f:
        verification = json.load(f)

    verified_ids = {v["_app_id"]: v for v in verification["details"]}

    final = []
    for r in research:
        app_id = r.get("_app_id")
        if app_id in verified_ids:
            v = verified_ids[app_id]
            r["_verification_status"] = "verified"
            r["_verification_agreed"] = v.get("agrees_with_original")
            if v.get("agrees_with_original") is False and v.get("disagreement_field"):
                field = v["disagreement_field"]
                if field in r:
                    r["_original_value_before_correction"] = {field: r[field]}
                    r[field] = v.get("your_finding", r[field])
                r["_correction_note"] = f"Corrected '{field}' during verification pass."
        else:
            r["_verification_status"] = "not_sampled"
        final.append(r)

    with open("output/research_final.json", "w") as f:
        json.dump(final, f, indent=2)

    verified_count = sum(1 for r in final if r.get("_verification_status") == "verified")
    corrected_count = sum(1 for r in final if "_correction_note" in r)

    print(f"Final dataset: {len(final)} apps.")
    print(f"{verified_count} were directly verified by a second pass.")
    print(f"{corrected_count} had a correction applied based on verification.")
    print("Saved to output/research_final.json")


if __name__ == "__main__":
    main()
