import os
import csv
from enverus_developer_api import DeveloperAPIv3


OUTPUT_FILE = "active_rigs.csv"


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
        return ""
    return value


def clean_date(value):
    if not value:
        return ""

    return str(value).split("T")[0]


def clean_number(value, decimals=6):
    if value is None or value == "":
        return ""

    try:
        return round(float(value), decimals)
    except ValueError:
        return value


def build_csv_row(row):
    return {
        "Rig Name": clean(row.get("RigName")),
        "Status": clean(row.get("ActiveStatus")),
        "Operator": clean(row.get("ENVOperator")),
        "County": clean(row.get("County")),
        "State": clean(row.get("StateProvince")),
        "Basin": clean(row.get("ENVBasin")),
        "Region": clean(row.get("ENVRegion")),
        "API Number": clean(row.get("API_UWI")),
        "Well ID": clean(row.get("WellID")),
        "Completion ID": clean(row.get("CompletionID")),
        "Latitude": clean_number(row.get("RigLatitudeWGS84")),
        "Longitude": clean_number(row.get("RigLongitudeWGS84")),
        "Spud Date": clean_date(row.get("SpudDate")),
        "Last Updated": clean_date(row.get("UpdatedDate")),
    }


def export_active_rigs_to_csv():
    api = create_api()

    print("Querying active rigs...")

    query = api.query(
        "rigs",
        deleteddate="null",
        pagesize=1000,
    )

    rows = []

    for row in query:
        rows.append(build_csv_row(row))

    if not rows:
        print("No active rig records found.")
        return

    rows.sort(
        key=lambda row: (
            row["State"],
            row["County"],
            row["Operator"],
            row["Rig Name"],
        )
    )

    headers = [
        "Rig Name",
        "Status",
        "Operator",
        "County",
        "State",
        "Basin",
        "Region",
        "API Number",
        "Well ID",
        "Completion ID",
        "Latitude",
        "Longitude",
        "Spud Date",
        "Last Updated",
    ]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} active rig records to {OUTPUT_FILE}")


def main():
    set_token_v3()
    export_active_rigs_to_csv()


if __name__ == "__main__":
    main()
