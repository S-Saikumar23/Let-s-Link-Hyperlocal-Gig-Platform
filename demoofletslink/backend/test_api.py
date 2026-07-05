import time
time.sleep(3)
import requests
r = requests.get('http://localhost:8000/api/tasks/')
print('Status:', r.status_code)
if r.status_code == 200:
    data = r.json()
    print(f'Tasks found: {len(data)}')
    for t in data:
        req_name = t.get('requester', {}).get('name', 'N/A') if t.get('requester') else 'N/A'
        print(f"  - '{t['title']}' | by: {req_name} | status: {t['status']}")
else:
    print('Error:', r.text[:500])
