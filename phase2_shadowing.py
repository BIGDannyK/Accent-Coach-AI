import os
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

# --- 설정 (Phase 1과 동일) ---
load_dotenv()
speech_key = os.environ.get('SPEECH_KEY')
speech_region = os.environ.get('SPEECH_REGION')
reference_text = "The weather is lovely today."

def speak_reference_text():
    """참조 텍스트를 원어민 음성으로 재생합니다."""
    print(f"\n[1] 원어민 발음 듣기...")
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    # 고품질의 자연스러운 음성 선택
    speech_config.speech_synthesis_voice_name = 'en-US-JennyNeural'
    
    # 스피커로 출력 설정
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
    
    result = speech_synthesizer.speak_text_async(reference_text).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("    재생 완료.")
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print(f"음성 합성이 취소되었습니다: {cancellation_details.reason}")

def assess_user_pronunciation():
    """사용자의 발음을 녹음하고 평가합니다."""
    print(f"\n[2] 이제 따라 말해보세요 (마이크 녹음 시작됨)...")
    
    # Phase 1의 발음 평가 로직과 거의 동일
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme
    )

    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    pronunciation_config.apply_to(speech_recognizer)
    
    result = speech_recognizer.recognize_once_async().get()

    # Phase 1의 결과 처리 로직과 동일
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print(f"\n인식된 텍스트: {result.text}")
        pronunciation_result = speechsdk.PronunciationAssessmentResult(result)
        print("\n--- 평가 결과 ---")
        print(f"  정확도: {pronunciation_result.accuracy_score}, 유창성: {pronunciation_result.fluency_score}")
        print("--- 단어별 상세 ---")
        for word in pronunciation_result.words:
            print(f"  '{word.word}' \t정확도: {word.accuracy_score} \t오류: {word.error_type}")
    # ... (Phase 1의 에러 처리 부분 생략) ...

if __name__ == "__main__":
    print(f"쉐도잉 연습 문장: '{reference_text}'")
    # 1. 원어민 발음 듣기
    speak_reference_text()
    # 2. 사용자 발음 평가
    assess_user_pronunciation()