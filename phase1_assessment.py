import os
import json
import random
import requests
from openai import AzureOpenAI
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

# --- 환경 변수 로드 ---
load_dotenv()
AZURE_SEARCH_NAME = os.getenv("AZURE_SEARCH_SERVICE")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
AZURE_SEARCH_INDEX = "idx-friends-rag"
AZURE_SEARCH_API = "2023-11-01"

# --- OpenAI 클라이언트 설정 ---
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version="2024-05-01-preview"
)

def search_index(query, top=5):
    url = f"https://{AZURE_SEARCH_NAME}.search.windows.net/indexes/{AZURE_SEARCH_INDEX}/docs/search?api-version={AZURE_SEARCH_API}"
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_SEARCH_KEY
    }
    payload = {
        "search": query,
        "queryType": "semantic",
        "top": top,
        "select": "content,file_name"
    }
    r = requests.post(url, headers=headers, data=json.dumps(payload))
    if r.status_code != 200:
        print("❌ Azure Search 오류:", r.text)
        return []
    return r.json().get("value", [])

# --- 1) OpenAI에게 검색 키워드 추천 ---
print("🔎 OpenAI에게 추천 문장을 요청합니다...")
response = client.chat.completions.create(
    model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    messages=[
        {"role": "system", "content": "당신은 영어 학습 코치입니다. Friends 대본에서 발음 연습용으로 적당한 짧은 대사를 찾기 위한 검색어를 추천하세요."},
        {"role": "user", "content": "추천할만한 짧고 유용한 대사 하나를 골라줘. 구체적인 문장이 아니라 검색에 쓸만한 키워드로."}
    ],
    max_tokens=30
)
search_query = response.choices[0].message.content.strip()
print(f"🧠 OpenAI 추천 검색어: \"{search_query}\"")

# --- 2) Azure Search 검색 ---
results = search_index(search_query)
if not results:
    print("⚠️ 검색 결과가 없습니다. fallback 문장 사용합니다.")
    reference_text = "How are you doing today?"
else:
    # 여러 문서에서 랜덤으로 chunk 하나 뽑기
    candidates = []
    for doc in results:
        if isinstance(doc.get("content"), list):
            candidates.extend(doc["content"])
    if not candidates:
        reference_text = "Nice to meet you!"
    else:
        # 5개 후보 랜덤 선택 후 OpenAI에게 "발음 연습용"으로 가장 적합한 것 고르게 시킴
        sampled = random.sample(candidates, min(5, len(candidates)))
        joined_text = "\n".join(f"- {c}" for c in sampled)

        refinement = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            messages=[
                {"role": "system", "content": "당신은 영어 발음 교정 전문가입니다. 주어진 문장 중에서 발음 연습에 가장 적합한 문장을 1개만 고르세요."},
                {"role": "user", "content": f"후보 문장:\n{joined_text}\n\n발음 연습하기에 좋은 문장을 하나만 골라서 그대로 출력해줘."}
            ],
            max_tokens=60
        )
        reference_text = refinement.choices[0].message.content.strip()

print(f"🎯 최종 발음 평가 문장: {reference_text}")

# --- 3) Azure Speech 발음 평가 ---
speech_key = os.getenv("SPEECH_KEY")
speech_region = os.getenv("SPEECH_REGION")
speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
speech_config.speech_recognition_language = "en-US"

audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
pronunciation_config = speechsdk.PronunciationAssessmentConfig(
    reference_text=reference_text,
    grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
    granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme
)

recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
print("\n🎙️ 마이크로 문장을 읽으세요...")
pronunciation_config.apply_to(recognizer)

result = recognizer.recognize_once()
if result.reason == speechsdk.ResultReason.RecognizedSpeech:
    print(f"✅ 인식된 문장: {result.text}")
    print(f"📊 발음 평가 결과: {result.properties[speechsdk.PropertyId.SpeechServiceResponse_JsonResult]}")
else:
    print(f"❌ 인식 실패: {result.reason}")
