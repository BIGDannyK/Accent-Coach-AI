import os, json, requests
from dotenv import load_dotenv
load_dotenv()

SEARCH_NAME = os.environ["AZ_SEARCH_NAME"]
ADMIN_KEY   = os.environ["AZ_SEARCH_ADMIN_KEY"]
STORAGE_CONN = os.environ["AZ_STORAGE_CONN"]
CONTAINER    = os.environ["AZ_STORAGE_CONTAINER"]

API  = "2023-11-01"
BASE = f"https://{SEARCH_NAME}.search.windows.net"
HDRS = {"api-key": ADMIN_KEY, "Content-Type": "application/json"}

DS_NAME       = "ds-friendsscript"
INDEX_NAME    = "idx-friends-rag"
SKILLSET_NAME = "ss-friends-rag"
INDEXER_NAME  = "ixr-friends-rag"

def upsert(url, body):
    r = requests.put(url, headers=HDRS, data=json.dumps(body))
    ok = r.status_code in (200,201)
    print(("✅" if ok else "⚠️"), url.split("/")[-1], r.status_code, r.text if not ok else "")
    return ok, r.text

# 1) Data Source (PUT = create or update)
def create_or_update_datasource():
    url = f"{BASE}/datasources/{DS_NAME}?api-version={API}"
    body = {
        "name": DS_NAME,
        "type": "azureblob",
        "credentials": {"connectionString": STORAGE_CONN},
        "container": {"name": CONTAINER}
    }
    upsert(url, body)

# 2) Index (semanticSettings + analyzer)
def create_or_update_index():
    url = f"{BASE}/indexes/{INDEX_NAME}?api-version={API}"
    body = {
        "name": INDEX_NAME,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": False, "sortable": False},
            {"name": "content", "type": "Edm.String", "searchable": True, "analyzer": "en.microsoft"},
            {"name": "file_name", "type": "Edm.String", "searchable": True},
            {"name": "file_path", "type": "Edm.String", "searchable": True},
            {"name": "content_type", "type": "Edm.String", "filterable": True},
            {"name": "language", "type": "Edm.String", "filterable": True},
            {"name": "last_modified", "type": "Edm.DateTimeOffset", "filterable": True, "sortable": True}
        ],
        # ✅ 2023-11-01에서는 'semantic' 사용, 그리고 'prioritizedContentFields'
        "semantic": {
            "configurations": [
                {
                    "name": "sem-config",
                    "prioritizedFields": {
                        "titleField": {"fieldName": "file_name"},
                        "prioritizedContentFields": [{"fieldName": "content"}]
                        # 필요하면 "prioritizedKeywordsFields": [{"fieldName":"tags"}] 추가
                    }
                }
            ]
        }
    }
    r = requests.put(url, headers=HDRS, data=json.dumps(body))
    ok = r.status_code in (200, 201)
    print(("✅" if ok else "⚠️"), "index", r.status_code, "" if ok else r.text)

# 3) Skillset (file_data 입력 경로)
def create_or_update_skillset():
    url = f"{BASE}/skillsets/{SKILLSET_NAME}?api-version={API}"
    body = {
        "name": SKILLSET_NAME,
        "description": "Language detect + sentence split for RAG (rely on built-in cracking)",
        "skills": [
            {
                "@odata.type":"#Microsoft.Skills.Text.LanguageDetectionSkill",
                "inputs":[{"name":"text","source":"/document/content"}],
                "outputs":[{"name":"languageCode","targetName":"language"}]
            },
            {
                "@odata.type":"#Microsoft.Skills.Text.SplitSkill",
                "textSplitMode":"sentences",
                "maximumPageLength": 1800,
                "inputs":[{"name":"text","source":"/document/content"}],
                "outputs":[{"name":"textItems","targetName":"chunks"}]
            }
        ]
    }
    r = requests.put(url, headers=HDRS, data=json.dumps(body))
    ok = r.status_code in (200,201)
    print(("✅" if ok else "⚠️"), "skillset", r.status_code, "" if ok else r.text)


# 4) Indexer (id 채우기 + 매핑)
def create_or_update_indexer():
    url = f"{BASE}/indexers/{INDEXER_NAME}?api-version={API}"
    body = {
        "name": INDEXER_NAME,
        "dataSourceName": DS_NAME,
        "targetIndexName": INDEX_NAME,
        "skillsetName": SKILLSET_NAME,
        "fieldMappings": [
            {"sourceFieldName":"metadata_storage_name","targetFieldName":"file_name"},
            {"sourceFieldName":"metadata_storage_path","targetFieldName":"file_path"},
            {"sourceFieldName":"metadata_content_type","targetFieldName":"content_type"},
            {"sourceFieldName":"metadata_storage_last_modified","targetFieldName":"last_modified"},
            {   # 인덱스 key 채우기
                "sourceFieldName":"metadata_storage_path",
                "targetFieldName":"id",
                "mappingFunction":{"name":"base64Encode"}
            }
        ],
        "outputFieldMappings": [
            {"sourceFieldName":"/document/language","targetFieldName":"language"},
            {"sourceFieldName":"/document/chunks/*","targetFieldName":"content"}
        ],
        "parameters": {
            "configuration": {
                "dataToExtract":"contentAndMetadata",
                "imageAction":"generateNormalizedImages"
            }
        },
        "schedule":{"interval":"PT1H"}
    }
    upsert(url, body)

def run_indexer():
    url = f"{BASE}/indexers/{INDEXER_NAME}/run?api-version={API}"
    r = requests.post(url, headers={"api-key": ADMIN_KEY})
    print(("✅" if r.status_code in (200,202) else "⚠️"), "run", r.status_code, r.text if r.status_code not in (200,202) else "")

if __name__ == "__main__":
    create_or_update_datasource()
    create_or_update_index()
    create_or_update_skillset()
    create_or_update_indexer()
    run_indexer()
