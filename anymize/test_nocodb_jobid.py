#!/usr/bin/env python3
import requests, uuid, os

def main():
    # Load config
    from config_shared import NOCODB_BASE, NOCODB_TOKEN
    table_id = "mun2eil6g6a3i25"
    headers = {"xc-token": NOCODB_TOKEN, "Content-Type": "application/json"}
    create_url = f"{NOCODB_BASE}/api/v2/tables/{table_id}/records"
    fetch_url = create_url

    # 1. Create job row with custom job_id
    job_id = str(uuid.uuid4())[:8]
    payload = {
        'internal_ID': str(uuid.uuid4()),
        'job_id': job_id,
        'input_text': 'Test input',
        'output_text': ''
    }
    print(f"Creating record with job_id={job_id}")
    r = requests.post(create_url, json=payload, headers=headers)
    r.raise_for_status()
    rec = r.json()
    record_id = rec.get('Id') or rec.get('id')
    print("Created record Id:", record_id)

    # 2. Update sample data in the row
    # Use PATCH endpoint without recordId in URL, include Id in body
    update_url = create_url
    update_payload = {'Id': record_id, 'output_text': 'SAMPLE_OUTPUT'}
    print("Updating record output_text to SAMPLE_OUTPUT")
    ru = requests.patch(update_url, json=update_payload, headers=headers)
    ru.raise_for_status()
    print("Update response:", ru.json())

    # 3. Fetch via custom job_id
    print("Fetching by job_id via GET with params:", {'where': f'(job_id,eq,{job_id})'})
    try:
        fr = requests.get(fetch_url, params={'where': f'(job_id,eq,{job_id})'}, headers=headers)
        fr.raise_for_status()
        data = fr.json().get('list', [])
        print("Fetch result list:", data)
        if data and data[0].get('output_text') == 'SAMPLE_OUTPUT':
            print("✅ Success: can fetch updated row by job_id")
        else:
            print("❌ Failure: row fetched but output_text mismatch or empty list")
    except Exception as e:
        print("❌ Error fetching by job_id:", repr(e), getattr(e, 'response', None).text if hasattr(e, 'response') else '')

if __name__ == '__main__':
    main()
