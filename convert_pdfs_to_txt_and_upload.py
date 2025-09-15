import os
import re
import io
from pathlib import Path
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from pypdf import PdfReader

# 1️⃣ 환경 변수 로드
load_dotenv()
AZ_STORAGE_CONN = os.getenv("AZ_STORAGE_CONN")
AZ_STORAGE_CONTAINER = os.getenv("AZ_STORAGE_CONTAINER")

if not AZ_STORAGE_CONN or not AZ_STORAGE_CONTAINER:
    raise RuntimeError("⚠️ AZ_STORAGE_CONN / AZ_STORAGE_CONTAINER 환경 변수를 확인하세요.")

# 2️⃣ Azure Blob 클라이언트 생성
blob_service_client = BlobServiceClient.from_connection_string(AZ_STORAGE_CONN)
container_client = blob_service_client.get_container_client(AZ_STORAGE_CONTAINER)

# 3️⃣ 로컬 파일 목록 (현재 디렉토리의 Friends SeasonXX_EnglishScript.pdf)
pdf_files = sorted(Path(".").glob("Friends Season*_EnglishScript.pdf"))

output_dir = Path("txt_output")
output_dir.mkdir(exist_ok=True)

def clean_text(text):
    """불필요한 공백/페이지번호 제거 & 줄 단위 대사 유지"""
    text = re.sub(r'\s+', ' ', text)  # 여러 공백 → 하나
    text = text.strip()
    return text

for pdf_path in pdf_files:
    print(f"📄 Converting {pdf_path.name} ...")
    reader = PdfReader(str(pdf_path))
    all_lines = []

    for page in reader.pages:
        page_text = page.extract_text()
        if not page_text:
            continue
        lines = page_text.split("\n")
        for line in lines:
            line = clean_text(line)
            if line:
                all_lines.append(line)

    # TXT 파일 저장
    txt_name = pdf_path.stem.replace(" ", "_") + ".txt"
    txt_path = output_dir / txt_name
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(all_lines))
    print(f"✅ Saved {txt_name} ({len(all_lines)} lines)")

    # Azure Blob 업로드
    blob_client = container_client.get_blob_client(txt_name)
    with open(txt_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)
    print(f"☁️ Uploaded to Azure Blob: {txt_name}")

print("\n🎉 변환 및 업로드 완료! 이제 recreate_index_and_reindex.py 실행해서 다시 인덱싱하세요.")