import os
import time
import azure.cognitiveservices.speech as speechsdk
from openai import AzureOpenAI
from dotenv import load_dotenv
import pyaudio
import wave
import numpy as np # 1. numpy import 추가

# --- 설정 및 초기화 ---

def initialize_app():
    """모든 설정을 로드하고 클라이언트를 초기화합니다."""
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
    
    system_prompt = "You are a friendly and patient barista at a coffee shop named Alex. Keep your responses very short and clear. Start the conversation by greeting the customer and asking what they would like."
    conversation_history = [{"role": "system", "content": system_prompt}]
    
    print("✅ AI 대화 엔진 초기화 완료.")

# --- 보조 함수 ---

def speak_text(text):
    """주어진 텍스트를 AI 음성으로 출력합니다."""
    print(f"\n[AI Alex]: {text}")
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
    synthesizer.speak_text_async(text).get()

def get_ai_response():
    """Azure OpenAI를 호출하여 AI의 응답을 받아옵니다."""
    print("\nAI가 응답을 생각 중입니다...")
    response = openai_client.chat.completions.create(
        model=openai_deployment_name,
        messages=conversation_history
    )
    message = response.choices[0].message.content
    conversation_history.append({"role": "assistant", "content": message})
    return message

# 2. '자동 중단' 기능이 포함된 새로운 record_audio 함수
def record_audio(filename, silence_threshold=500, silence_duration=1.5, rate=16000):
    """
    사용자가 말하기 시작하면 녹음을 시작하고,
    일정 시간 동안 말이 없으면 자동으로 녹음을 중단합니다.
    """
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
    """오디오 파일을 녹음한 후, 해당 파일을 Azure로 보내 분석합니다."""
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
    pronunciation_details = speechsdk.PronunciationAssessmentResult(assessment_result)
    
    print("\n--- 📊 발음 평가 결과 ---")
    print(f"  - 정확도: {pronunciation_details.accuracy_score}")
    print(f"  - 유창성: {pronunciation_details.fluency_score}")
    print("-------------------------")

    return user_text

# --- 메인 대화 루프 ---

def main():
    try:
        initialize_app()
        ai_response = get_ai_response()
        speak_text(ai_response)

        while True:
            user_response = process_user_speech()
            if user_response:
                # 3. 개선된 대화 종료 로직
                exit_keywords = ["goodbye", "exit", "that's all", "i'm done"]
                if any(keyword in user_response.lower() for keyword in exit_keywords):
                    speak_text("Alright, ending our session. You did a great job!")
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