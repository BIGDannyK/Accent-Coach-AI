import os
import time
import azure.cognitiveservices.speech as speechsdk
from openai import AzureOpenAI
from dotenv import load_dotenv
import pyaudio
import wave
import numpy as np
from collections import Counter

# --- 설정 및 초기화 ---

PROMPTS = {
    "1": {
        "title": "카페에서 주문하기",
        "prompt": "You are a friendly and patient barista at a coffee shop named Alex. Keep your responses very short and clear. Start the conversation by greeting the customer and asking what they would like."
    },
    "2": {
        "title": "직업 인터뷰 자기소개",
        "prompt": "You are a hiring manager named Sarah conducting a job interview. Keep your responses professional and concise. Start the interview by saying, 'Thanks for coming in today. Could you start by telling me a little about yourself?'"
    },
    "3": {
        "title": "호텔 체크인하기",
        "prompt": "You are a hotel receptionist named Ben. Be polite and efficient. Start the conversation by greeting the guest with, 'Welcome to the Gemini Hotel. How can I help you today?'"
    },
    "4": {
        "title": "길 물어보기",
        "prompt": "You are a helpful local person in New York City. A tourist has just approached you. Start the conversation by asking, 'Are you looking for something?'"
    },
    "5": {
        "title": "병원 예약하기",
        "prompt": "You are a medical receptionist named Maria. Be calm and clear. Start the conversation by saying, 'Good morning, City Clinic. How may I help you?'"
    }
}

session_feedback = []

def initialize_app(system_prompt):
    load_dotenv()
    
    global speech_config
    speech_key = os.environ.get('SPEECH_KEY')
    speech_region = os.environ.get('SPEECH_REGION')
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    speech_config.speech_synthesis_voice_name = 'en-US-JennyNeural'

    global openai_client, openai_deployment_name, conversation_history
    openai_deployment_name = os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME')
    openai_client = AzureOpenAI(
        azure_endpoint=os.environ.get('AZURE_OPENAI_ENDPOINT'),
        api_key=os.environ.get('AZURE_OPENAI_KEY'),
        api_version="2024-12-01-preview"
    )
    
    conversation_history = [{"role": "system", "content": system_prompt}]
    
    print("✅ AI 대화 엔진 초기화 완료.")

# --- 보조 함수 ---

def speak_text(text):
    print(f"\n[AI]: {text}")
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
    synthesizer.speak_text_async(text).get()

def get_ai_response():
    print("\nAI가 응답을 생각 중입니다...")
    response = openai_client.chat.completions.create(
        model=openai_deployment_name,
        messages=conversation_history
    )
    message = response.choices[0].message.content
    conversation_history.append({"role": "assistant", "content": message})
    return message

def record_audio(filename, silence_threshold=500, silence_duration=1.5, rate=16000):
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=rate, input=True, frames_per_buffer=CHUNK)
    print("\n🎙️  AI의 말을 듣고 대답해주세요. (말씀이 끝나면 자동으로 녹음이 중단됩니다...)")
    frames = []
    started = False
    silence_counter = 0
    while True:
        data = stream.read(CHUNK)
        amplitude = np.frombuffer(data, dtype=np.int16).max()
        if amplitude > silence_threshold:
            if not started:
                print("... 말소리가 감지되어 녹음을 시작합니다.")
                started = True
            frames.append(data)
            silence_counter = 0
        elif started:
            frames.append(data)
            silence_counter += 1
            if silence_counter > int(rate / CHUNK * silence_duration):
                print("... 정적이 감지되어 녹음을 중단합니다.")
                break
    stream.stop_stream()
    stream.close()
    p.terminate()
    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(rate)
    wf.writeframes(b''.join(frames))
    wf.close()

# --- 핵심 기능: 사용자 음성 처리 ---

def process_user_speech():
    temp_audio_file = "temp_user_audio.wav"
    record_audio(temp_audio_file)
    
    audio_input_config = speechsdk.audio.AudioConfig(filename=temp_audio_file)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_input_config)
    stt_result = speech_recognizer.recognize_once_async().get()

    if not stt_result.text:
        print("음성을 인식하지 못했습니다. 더 크고 명확하게 말씀해주세요.")
        return None
        
    user_text = stt_result.text
    print(f"💬 [나의 답변]: {user_text}")
    conversation_history.append({"role": "user", "content": user_text})
    
    print("... 방금 한 말의 발음을 분석 중입니다 ...")
    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=user_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme
    )
    assessment_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_input_config)
    pronunciation_config.apply_to(assessment_recognizer)
    
    assessment_result = assessment_recognizer.recognize_once_async().get()
    
    if assessment_result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult) is None:
        print("\n❌ 오류: Azure로부터 발음 평가 결과를 받지 못했습니다.")
        return user_text

    pronunciation_details = speechsdk.PronunciationAssessmentResult(assessment_result)
    
    # <-- 변경된 부분: 실시간 피드백을 더 상세하게 표시 -->
    print("\n--- 📊 실시간 발음 피드백 ---")
    print(f"  - Pronunciation Score: {pronunciation_details.pronunciation_score}")
    print("  -------------------------")
    print(f"  - Accuracy Score:    {pronunciation_details.accuracy_score}")
    print(f"  - Fluency Score:     {pronunciation_details.fluency_score}")
    print(f"  - Completeness Score: {pronunciation_details.completeness_score}")
    print(f"  - Prosody Score:      {pronunciation_details.prosody_score}")

    error_counter = Counter(word.error_type for word in pronunciation_details.words)
    mispronounced_words = [word.word for word in pronunciation_details.words if word.error_type == 'Mispronunciation']

    print("\n  --- 에러 분석 ---")
    print(f"  - 잘못된 발음 (Mispronunciation): {error_counter['Mispronunciation']}개")
    if mispronounced_words:
        print(f"    - 해당 단어: {', '.join(mispronounced_words)}")
    print(f"  - 빠뜨린 단어 (Omission):        {error_counter['Omission']}개")
    print(f"  - 추가한 단어 (Insertion):       {error_counter['Insertion']}개")
    print("----------------------------")

    session_feedback.append(pronunciation_details)

    return user_text

# <-- 변경된 부분: 최종 요약 리포트 기능 강화 -->
def generate_final_summary(feedback_list):
    if not feedback_list:
        print("\n분석할 데이터가 없습니다.")
        return

    print("\n\n========================================")
    print("      📜 최종 발음 분석 리포트      ")
    print("========================================")

    # <-- 변경된 부분: sum 계산 시 'or 0'을 추가하여 None 값을 0으로 처리 -->
    # 1. 전체 평균 점수 계산
    avg_accuracy = sum(res.accuracy_score or 0 for res in feedback_list) / len(feedback_list)
    avg_fluency = sum(res.fluency_score or 0 for res in feedback_list) / len(feedback_list)
    avg_completeness = sum(res.completeness_score or 0 for res in feedback_list) / len(feedback_list)
    avg_prosody = sum(res.prosody_score or 0 for res in feedback_list) / len(feedback_list)
    
    print(f"\n📈 전체 대화 평균 점수:")
    print(f"   - 정확도: {avg_accuracy:.2f} / 100")
    print(f"   - 유창성: {avg_fluency:.2f} / 100")
    print(f"   - 완성도: {avg_completeness:.2f} / 100")
    print(f"   - 운율 점수: {avg_prosody:.2f} / 100")

    # 2. 전체 에러 유형별 합계
    total_errors = Counter()
    all_mispronounced_words = []
    for res in feedback_list:
        total_errors.update(word.error_type for word in res.words)
        for word in res.words:
            if word.error_type == 'Mispronunciation':
                all_mispronounced_words.append(word.word.lower())

    print(f"\n🔍 전체 에러 분석:")
    print(f"   - 잘못된 발음: {total_errors['Mispronunciation']}개")
    print(f"   - 빠뜨린 단어: {total_errors['Omission']}개")
    print(f"   - 추가한 단어: {total_errors['Insertion']}개")

    if all_mispronounced_words:
        word_counts = Counter(all_mispronounced_words)
        print(f"\n🤔 가장 자주 틀린 단어 TOP 3:")
        for i, (word, count) in enumerate(word_counts.most_common(3)):
            print(f"   {i+1}. '{word}' ({count}회)")
    else:
        print("\n🎉 전체 대화에서 틀린 단어가 없습니다! 완벽합니다!")
    
    print("\n앞으로도 꾸준히 연습해보세요!")
    print("========================================")


# --- 메인 대화 루프 ---
def main():
    try:
        print("=== 발음 교정 AI와 대화할 상황을 선택해주세요 ===")
        for key, value in PROMPTS.items():
            print(f"[{key}] {value['title']}")
        
        choice = ""
        while choice not in PROMPTS:
            choice = input("원하는 상황의 번호를 입력하세요: ")
        
        selected_prompt = PROMPTS[choice]['prompt']
        
        initialize_app(selected_prompt)
        ai_response = get_ai_response()
        speak_text(ai_response)

        while True:
            user_response = process_user_speech()
            if user_response:
                exit_keywords = ["goodbye", "exit", "that's all", "i'm done"]
                if any(keyword in user_response.lower() for keyword in exit_keywords):
                    speak_text("Alright, ending our session. You did a great job!")
                    generate_final_summary(session_feedback)
                    break
                ai_response = get_ai_response()
                speak_text(ai_response)
            else:
                speak_text("Sorry, I didn't catch that. Could you say it again?")
    except Exception as e:
        print(f"\n❌ 치명적인 에러 발생: {e}")
    finally:
        if os.path.exists("temp_user_audio.wav"):
            os.remove("temp_user_audio.wav")
        print("\n프로그램을 종료합니다.")

if __name__ == "__main__":
    main()