import os
import json
from enverus_developer_api import DeveloperAPIv3


OUTPUT_FILE = "active_rigs.json"


def set_token_v3():
    if os.environ.get("DIRECTACCESSV3_TOKEN"):
        print("Using existing DIRECTACCESSV3_TOKEN")
        return

    secret_key = os.environ.get("DIRECTACCESSV3_API_KEY")

    if not secret_key:
        raise RuntimeError(
            "Missing DIRECTACCESSV3_API_KEY.\n\n"
            "Set it first in PowerShell:\n"
            '$env:DIRECTACCESSV3_API_KEY="your_secret_key_here"'
        )

    api = DeveloperAPIv3(secret_key=secret_key)
    os.environ["DIRECTACCESSV3_TOKEN"] = api.access_token

    print("Token generated and saved to DIRECTACCESSV3_TOKEN")


def create_api():
    return DeveloperAPIv3(
        secret_key=os.environ.get("DIRECTACCESSV3_API_KEY"),
        access_token=os.environ.get("DIRECTACCESSV3_TOKEN"),
    )


def clean(value):
    if value is None or value == "":
        return None

    return value


def clean_date(value):
    if not value:
        return None

    return str(value).split("T")[0]


def clean_number(value, decimals=6):
    if value is None or value == "":
        return None

    try:
        return round(float(value), decimals)
    except ValueError:
        return value


def build_json_record(row):
    return {
        "rig_name": clean(row.get("RigName")),
        "status": clean(row.get("ActiveStatus")),
        "operator": clean(row.get("ENVOperator")),
        "location": {
            "county": clean(row.get("County")),
            "state": clean(row.get("StateProvince")),
            "basin": clean(row.get("ENVBasin")),
            "region": clean(row.get("ENVRegion")),
            "latitude": clean_number(row.get("RigLatitudeWGS84")),
            "longitude": clean_number(row.get("RigLongitudeWGS84")),
        },
        "identifiers": {
            "api_number": clean(row.get("API_UWI")),
            "well_id": clean(row.get("WellID")),
            "completion_id": clean(row.get("CompletionID")),
        },
        "dates": {
            "spud_date": clean_date(row.get("SpudDate")),
            "last_updated": clean_date(row.get("UpdatedDate")),
        },
    }


def export_active_rigs_to_json():
    api = create_api()

    print("Querying active rigs...")

    query = api.query(
        "rigs",
        deleteddate="null",
        pagesize=1000,
    )

    records = []

    for row in query:
        records.append(build_json_record(row))

    if not records:
        print("No active rig records found.")
        return

    records.sort(
        key=lambda row: (
            row["location"]["state"] or "",
            row["location"]["county"] or "",
            row["operator"] or "",
            row["rig_name"] or "",
        )
    )

    output = {
        "report_name": "Active Rigs Report",
        "source": "Enverus Developer API V3",
        "dataset": "rigs",
        "filter": {
            "deleteddate": "null"
        },
        "record_count": len(records),
        "records": records,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=4)

    print(f"Saved {len(records)} active rig records to {OUTPUT_FILE}")


def main():
    set_token_v3()
    export_active_rigs_to_json()


if __name__ == "__main__":
    main()