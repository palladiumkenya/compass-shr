import base64
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

FHIR_URL = os.environ.get("FHIR_URL", "http://fhir:8080")
AUTH_URL = os.environ.get("AUTH_URL", "http://compass-auth:7777")
CSV_PATH = os.environ.get("CSV_PATH", "/app/all_emr_sites.csv")


def wait_for_fhir():
    print("Waiting for FHIR server to be ready...")
    for attempt in range(40):
        try:
            urllib.request.urlopen(f"{FHIR_URL}/actuator/health", timeout=5)
            print("FHIR server is ready.")
            return
        except Exception:
            print(f"  Not ready yet (attempt {attempt + 1}/40), retrying in 15s...")
            time.sleep(15)
    sys.exit("ERROR: FHIR server did not become ready within 10 minutes.")


def get_token():
    raw = os.environ.get("CLIENTS", "[]")
    clients = json.loads(raw)
    if not clients:
        sys.exit("ERROR: CLIENTS env var is empty or missing.")
    client = clients[0]

    credentials = base64.b64encode(
        f"{client['username']}:{client['password']}".encode()
    ).decode()
    key = urllib.parse.quote(client["key"], safe="")
    url = f"{AUTH_URL}/v1/hie-auth?key={key}"

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {credentials}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode().strip()


def count_csv_rows():
    with open(CSV_PATH, newline="", encoding="latin-1") as f:
        return sum(1 for _ in csv.DictReader(f))


def fhir_organization_total(token):
    req = urllib.request.Request(f"{FHIR_URL}/fhir/Organization?_count=0&_total=accurate")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        bundle = json.loads(resp.read())
        return bundle.get("total", 0)


def build_organization(row):
    mfl_code = row["MFL_Code"].strip()
    lat_raw = row["Latitude"].strip()
    lon_raw = row["Longitude"].strip()

    address = {
        "district": row["SubCounty"].strip(),
        "state": row["County"].strip(),
        "country": "KE",
    }

    if lat_raw.lower() != "none" and lon_raw.lower() != "none":
        address["extension"] = [
            {
                "url": "http://hl7.org/fhir/StructureDefinition/geolocation",
                "extension": [
                    {"url": "latitude", "valueDecimal": float(lat_raw)},
                    {"url": "longitude", "valueDecimal": float(lon_raw)},
                ],
            }
        ]

    return {
        "resourceType": "Organization",
        "id": mfl_code,
        "identifier": [
            {
                "system": "https://kmhfl.health.go.ke",
                "value": mfl_code,
            }
        ],
        "active": True,
        "type": [{"text": row["Owner"].strip()}],
        "name": row["Facility_Name"].strip(),
        "address": [address],
    }


def put_organization(token, resource):
    mfl_code = resource["id"]
    url = f"{FHIR_URL}/fhir/Organization/{mfl_code}"
    data = json.dumps(resource).encode()
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/fhir+json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status


def main():
    wait_for_fhir()

    print("Obtaining JWT token...")
    token = get_token()
    print("Token obtained.")

    expected = count_csv_rows()
    current = fhir_organization_total(token)
    print(f"Facilities in CSV: {expected} | Organizations in FHIR: {current}")

    if current >= expected:
        print("Already fully seeded — skipping.")
        return

    print(f"Seeding facilities from {CSV_PATH}...")
    seeded = 0
    errors = 0

    with open(CSV_PATH, newline="", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            resource = build_organization(row)
            try:
                put_organization(token, resource)
                seeded += 1
                if seeded % 100 == 0:
                    print(f"  {seeded} facilities seeded...")
            except urllib.error.HTTPError as e:
                errors += 1
                print(f"  ERROR {e.code} for MFL {row['MFL_Code']}: {e.read().decode()[:200]}")
            except Exception as e:
                errors += 1
                print(f"  ERROR for MFL {row['MFL_Code']}: {e}")

    print(f"Done. Seeded {seeded} facilities. Errors: {errors}.")


if __name__ == "__main__":
    main()
