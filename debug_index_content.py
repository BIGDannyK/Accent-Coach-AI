import os, json, requests
from dotenv import load_dotenv

load_dotenv()

SERVICE = os.environ["AZ_SEARCH_NAME"]
API_KEY = os.environ["AZ_SEARCH_ADMIN_KEY"]
API = "2023-11-01"
BASE = f"https://{SERVICE}.search.windows.net"
INDEX = "idx-friends-rag"

url = f"{BASE}/indexes/{INDEX}/docs/search?api-version={API}"
headers = {"api-key": API_KEY, "Content-Type": "application/json"}
body = {
    "search": "*",  # 전체 문서
    "top": 3,
    "select": "id,file_name,content"
}

r = requests.post(url, headers=headers, data=json.dumps(body))
print("POST search ->", r.status_code)

if r.status_code == 200:
    docs = r.json().get("value", [])
    print(f"=== Retrieved {len(docs)} documents ===")
    for d in docs:
        print(f"\n📄 file: {d.get('file_name')}")
        c = d.get("content")
        if isinstance(c, list):
            print(f"  content: list of {len(c)} chunks")
            print("  sample:", str(c[:2]))
        else:
            print(f"  content type: {type(c)}")
            print(f"  content preview: {str(c)[:300]}")
else:
    print(r.text)
