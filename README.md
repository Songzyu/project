# Certi Mentor

`data/cert_data.json`을 검색해 자격증 정보를 정리하는 Streamlit 앱입니다. `rag_engine.py`가 JSON 데이터에서 질문과 가까운 자격증을 검색하고, Gemini API 키가 설정되어 있으면 Pydantic 스키마의 Structured Output으로 응답을 생성합니다. API 키가 없을 때는 로컬 데이터 검색으로 동작합니다.

## 시작하기

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

프로젝트 루트의 `.env` 파일에 Gemini API 키를 설정합니다.

```dotenv
GEMINI_API_KEY=발급받은_API_키
```

그 다음 웹 앱을 실행합니다.

```powershell
streamlit run app.py
```

또는 `python app.py`로 실행해도 됩니다.

기본 모델은 `gemini-2.5-flash`입니다. 필요하면 `.env`에 `GEMINI_MODEL=모델명`을 설정할 수 있습니다. `.env`와 API 키는 Git에 포함되지 않습니다.

## 데이터 범위

현재 데이터셋에는 자격증명, 분류, 종류, 난이도, 개요, 관련 기술 및 직무가 있습니다. 응시 조건, 시험 과목, 가산점 정보는 포함되어 있지 않아 임의로 생성하지 않고 미수록으로 표시합니다. 최신 세부 정보는 자격증 공식 시행기관에서 확인해 주세요.
