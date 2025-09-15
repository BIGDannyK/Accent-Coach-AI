import os
import time
import json
import requests
import argparse
from dotenv import load_dotenv

load_dotenv()

SEARCH_SERVICE = os.environ["AZURE_SEARCH_SERVICE"]
API_KEY = os.environ["AZURE_SEARCH_ADMIN_KEY"]
DATASOURCE_NAME = "ds-friends-rag"

HEADERS = {"Content-Type": "application/json", "api-key": API_KEY}

def put(url, body):
    r = requests.put(url, headers=HEADERS, data=json.dumps(body))
    print(f"PUT {url} -> {r.status_code}")
    if r.status_code >= 300:
        print(r.text)
    return r

def post(url, body=None):
    r = requests.post(url, headers=HEADERS, data=json.dumps(body) if body else None)
    print(f"POST {url} -> {r.status_code}")
    if r.status_code >= 300:
        print(r.text)
    return r

def delete(url):
    r = requests.delete(url, headers=HEADERS)
    print(f"DELETE {url} -> {r.status_code}")
    return r

INDEX_URL = f"https://{SEARCH_SERVICE}.search.windows.net/indexes/idx-friends-rag?api-version=2023-11-01"
INDEX_BODY = {
    "name": "idx-friends-rag",
    "fields": [
        {"name": "id", "type": "Edm.String", "key": True, "searchable": True},
        {"name": "file_name", "type": "Edm.String", "searchable": True, "filterable": True},
        {"name": "file_path", "type": "Edm.String", "searchable": False, "filterable": True},
        {"name": "content", "type": "Collection(Edm.String)", "searchable": True, "filterable": False},
    ]
}

SKILLSET_URL = f"https://{SEARCH_SERVICE}.search.windows.net/skillsets/ss-friends-rag?api-version=2023-11-01"
SKILLSET_BODY = {
    "name": "ss-friends-rag",
    "description": "Split text files into chunks",
    "skills": [
        {
            "@odata.type": "#Microsoft.Skills.Text.SplitSkill",
            "name": "#1-split",
            "description": "Split text into 4000-character chunks",
            "context": "/document",
            "textSplitMode": "pages",
            "maximumPageLength": 4000,
            "inputs": [{"name": "text", "source": "/document/content"}],
            "outputs": [{"name": "textItems", "targetName": "final_chunks"}],
        }
    ]
}

INDEXER_URL = f"https://{SEARCH_SERVICE}.search.windows.net/indexers/idxr-friends-rag?api-version=2023-11-01"
INDEXER_BODY = {
    "name": "idxr-friends-rag",
    "dataSourceName": DATASOURCE_NAME,
    "targetIndexName": "idx-friends-rag",
    "skillsetName": "ss-friends-rag",
    "fieldMappings": [
        {"sourceFieldName": "metadata_storage_name", "targetFieldName": "file_name"},
        {"sourceFieldName": "metadata_storage_path", "targetFieldName": "file_path"},
    ],
    "outputFieldMappings": [
        {"sourceFieldName": "/document/final_chunks/*", "targetFieldName": "content"}
    ]
}

# 1. 재생성
print("🔄 Recreating index...")
delete(INDEX_URL)
put(INDEX_URL, INDEX_BODY)
put(SKILLSET_URL, SKILLSET_BODY)
put(INDEXER_URL, INDEXER_BODY)

# 2. 리셋 & 실행
RESET_URL = f"https://{SEARCH_SERVICE}.search.windows.net/indexers/idxr-friends-rag/reset?api-version=2023-11-01"
RUN_URL = f"https://{SEARCH_SERVICE}.search.windows.net/indexers/idxr-friends-rag/run?api-version=2023-11-01"
post(RESET_URL)
post(RUN_URL)

# 3. 상태 폴링
STATUS_URL = f"https://{SEARCH_SERVICE}.search.windows.net/indexers/idxr-friends-rag/status?api-version=2023-11-01"
print("\n⏳ Polling indexer status...")
while True:
    r = requests.get(STATUS_URL, headers=HEADERS)
    data = r.json()
    last = data.get("lastResult", {})
    status = last.get("status", "unknown")
    processed = last.get("itemsProcessed", 0)
    failed = last.get("itemsFailed", 0)
    print(f"status={status}, itemsProcessed={processed}, itemsFailed={failed}")
    if status not in ("inProgress", "running"):
        break
    time.sleep(5)

if status == "success":
    print("\n✅ Indexing complete!")
else:
    print("\n❌ Indexing failed or incomplete.")
    print(json.dumps(last, indent=2))

# 4. 옵션: 테스트 검색
parser = argparse.ArgumentParser()
parser.add_argument("--test", action="store_true", help="Run a sample search after reindex")
parser.add_argument("--query", type=str, default="Rachel", help="Search query string")
args = parser.parse_args()

if args.test and status == "success":
    SEARCH_URL = f"https://{SEARCH_SERVICE}.search.windows.net/indexes/idx-friends-rag/docs/search?api-version=2023-11-01"
    print(f"\n🔎 Testing search for '{args.query}'...")
    body = {"search": args.query, "top": 5, "select": "file_name, content"}
    r = requests.post(SEARCH_URL, headers=HEADERS, data=json.dumps(body))
    print(f"POST search -> {r.status_code}")
    if r.status_code == 200:
        results = r.json().get("value", [])
        print(f"=== Search results ({len(results)}) ===")
        for i, doc in enumerate(results, 1):
            snippet = (doc.get("content") or "")[:150].replace("\n", " ")
            print(f"{i:02d}. 📄 {doc.get('file_name')} :: {snippet}...")
    else:
        print(r.text)
