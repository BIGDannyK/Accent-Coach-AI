# Accent Coach AI

대화형 음성 AI 코칭 애플리케이션

## Overview
Azure Cognitive Services와 RAG 파이프라인을 활용하여 구축한 사용자 맞춤형 영어 억양 교정 및 회화 시스템입니다. 클라우드 환경에서 STT와 TTS, LLM을 연동하여, 사용자의 발화를 실시간으로 인식하고 피드백을 제공하는 End-to-End 음성 AI 파이프라인을 설계했습니다.

## Tech Stack
- Language: Python
- Cloud & Infra: Azure OpenAI, Azure Cognitive Search (AI Search), Azure Speech SDK

## System Architecture & Pipeline
대용량 텍스트 데이터를 벡터화하여 검색 증강 생성(RAG)을 수행하는 백엔드 파이프라인입니다.

- Data Ingestion: 프렌즈(Friends) 시즌 1~10 대본 데이터를 텍스트로 추출 및 전처리하여 Azure Blob Storage에 적재 (convert_pdfs_to_txt_and_upload.py)
- Vector Indexing: 전처리된 데이터를 분할 및 임베딩하여 Azure AI Search에 벡터 인덱스 생성 (setup_rag_index.py, recreate_index_and_reindex.py)
- Real-time Processing: 사용자의 음성을 STT로 텍스트화한 후, RAG 기반으로 컨텍스트를 구성하여 Azure OpenAI에 전달하고 TTS로 음성 코칭 반환

## Core Features
사용자의 학습을 돕는 총 3단계의 과정으로 구성되어 있습니다.

- Phase 1. Assessment (phase1_assessment.py)
  Azure Speech SDK를 활용하여 실시간 음성을 인식(STT)합니다. 사용자의 발음 및 억양 정확도를 평가하여 정량적 피드백을 제공합니다.
  
- Phase 2. Shadowing (phase2_shadowing.py)
  프렌즈 대본 RAG 지식 베이스를 활용하여 섀도잉 훈련을 진행합니다. 원어민 오디오(TTS) 출력 후, 사용자의 발화를 비교 분석하여 교정 포인트를 제시합니다.
  
- Phase 3. Conversation (phase3_conversation.py)
  Azure OpenAI를 기반으로 실시간 프리토킹 및 상황극을 진행합니다. 대화 문맥을 유지하며 어색한 표현과 억양을 실시간으로 교정하는 코칭을 수행합니다.
