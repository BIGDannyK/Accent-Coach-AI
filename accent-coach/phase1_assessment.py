import os
import json
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드 (보안을 위해 권장)
load_dotenv()

# --- 설정 ---
# Azure Portal에서 복사한 키와 지역 정보를 입력하세요.
# .env 파일에 아래와 같이 저장하거나, 직접 문자열로 입력할 수 있습니다.

speech_key = os.environ.get('SPEECH_KEY')
speech_region = os.environ.get('SPEECH_REGION')

# 평가할 참조 텍스트
reference_text = "The quick brown fox jumps over the lazy dog."

def pronunciation_assessment_from_mic():
    """마이크 입력을 받아 발음 평가를 수행합니다."""

    # Speech SDK 설정
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)

    # 발음 평가 설정
    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue="True"
    )

    # Speech Recognizer 객체 생성
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, 
        audio_config=audio_config
    )
    pronunciation_config.apply_to(speech_recognizer)

    print(f"다음 문장을 따라 읽어보세요:\n'{reference_text}'")
    print("\n말씀을 시작하면 녹음이 시작됩니다...")

    # 음성 인식 시작 (1회)
    result = speech_recognizer.recognize_once_async().get()

    # 결과 처리
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print(f"\n인식된 텍스트: {result.text}")
        
        # 발음 평가 결과 (JSON 형태) 추출
        pronunciation_result = speechsdk.PronunciationAssessmentResult(result)
        
        print("\n--- 전체 평가 결과 ---")
        print(f"  정확도 점수: {pronunciation_result.accuracy_score}")
        print(f"  유창성 점수: {pronunciation_result.fluency_score}")
        print(f"  운율 점수:   {pronunciation_result.prosody_score}")
        print(f"  완성도 점수: {pronunciation_result.completeness_score}")
        
        print("\n--- 단어별 상세 평가 ---")
        for word in pronunciation_result.words:
            print(f"  단어: '{word.word}' \t정확도: {word.accuracy_score} \t오류 유형: {word.error_type}")

    elif result.reason == speechsdk.ResultReason.NoMatch:
        print("음성을 인식할 수 없습니다.")
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print(f"음성 인식이 취소되었습니다: {cancellation_details.reason}")
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print(f"에러 상세: {cancellation_details.error_details}")

if __name__ == "__main__":
    # .env 파일 사용을 위해 pip install python-dotenv 필요
    try:
        pronunciation_assessment_from_mic()
    except Exception as e:
        print(f"스크립트 실행 중 에러 발생: {e}")
        print("SPEECH_KEY와 SPEECH_REGION 환경 변수가 올바르게 설정되었는지 확인하세요.")