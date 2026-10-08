from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


DATA_PATH = Path(__file__).resolve().parent / "data" / "cert_data.json"


class CertificateRecord(BaseModel):
    # cert_data.json의 summary, description, tags 등 유연한 필드 허용
    model_config = ConfigDict(extra="ignore")

    id: str
    category: str
    type: str
    names: list[str] = Field(default_factory=list)
    difficulty: str = "보통"
    tool_or_lang: list[str] = Field(default_factory=list)
    description: str = ""
    target_jobs: list[str] = Field(default_factory=list)


class CertificateDetails(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    category: str
    qualification_type: str
    overview: str
    difficulty: str
    related_tools: list[str] = Field(default_factory=list)
    target_jobs: list[str] = Field(default_factory=list)
    eligibility: str | None = None
    exam_subjects: list[str] | None = None
    bonus_benefits: list[str] | None = None


class CertificateMatch(BaseModel):
    certificate: CertificateRecord
    matched_name: str
    score: float


class CertificateNotFoundError(LookupError):
    pass


def load_certificates(path: Path = DATA_PATH) -> list[CertificateRecord]:
    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"자격증 데이터 파일을 찾을 수 없습니다: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"자격증 데이터 JSON 형식이 올바르지 않습니다: {exc}") from exc

    if not isinstance(raw_data, list):
        raise RuntimeError("자격증 데이터의 최상위 값은 JSON 배열이어야 합니다.")

    certificates: list[CertificateRecord] = []
    for item in raw_data:
        # cert_data.json에 'names' 필드가 없거나 비어있는 경우 호환 처리
        if "names" not in item or not item["names"]:
            if "name" in item:
                item["names"] = [item["name"]]
            elif "names" not in item:
                item["names"] = []

        # cert_data.json의 'tags'나 'summary'를 tool_or_lang으로 보완
        if "tool_or_lang" not in item:
            item["tool_or_lang"] = item.get("tags", [])

        try:
            cert = CertificateRecord.model_validate(item)
            certificates.append(cert)
        except ValidationError as exc:
            raise RuntimeError(f"자격증 데이터 필드 형식이 올바르지 않습니다 ({item.get('id', 'unknown')}): {exc}") from exc

    ids = [certificate.id for certificate in certificates]
    if len(ids) != len(set(ids)):
        raise RuntimeError("자격증 데이터에 중복된 id가 있습니다.")
    return certificates


def _normalize(text: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", text.casefold())


def _query_terms(query: str) -> str:
    normalized = _normalize(query)
    return re.sub(
        r"(자격증|자격|에대해|대해서|알려줘|설명해줘|설명|궁금해|찾아줘)",
        "",
        normalized,
    )


def _similarity(query: str, name: str) -> float:
    if not query or not name:
        return 0.0
    if name in query or query in name:
        return 1.0

    window_sizes = range(max(1, len(name) - 2), len(name) + 3)
    return max(
        (
            SequenceMatcher(None, name, query[index : index + size]).ratio()
            for size in window_sizes
            for index in range(max(1, len(query) - size + 1))
        ),
        default=0.0,
    )


def retrieve_certificate(
    query: str, certificates: list[CertificateRecord], threshold: float = 0.3
) -> CertificateMatch:
    query_terms = _query_terms(query)
    if not query_terms:
        raise CertificateNotFoundError("자격증 이름을 질문에 포함해 주세요.")

    best_match: CertificateMatch | None = None
    for certificate in certificates:
        for name in certificate.names:
            score = _similarity(query_terms, _normalize(name))
            if best_match is None or score > best_match.score:
                best_match = CertificateMatch(
                    certificate=certificate,
                    matched_name=name,
                    score=score,
                )

    if best_match is None or best_match.score < threshold:
        raise CertificateNotFoundError(
            "데이터셋에서 일치하는 자격증을 찾지 못했습니다. 자격증 이름을 확인해 주세요."
        )
    return best_match


def _trusted_details(
    certificate: CertificateRecord, matched_name: str, overview: str
) -> CertificateDetails:
    return CertificateDetails(
        id=certificate.id,
        name=matched_name,
        category=certificate.category,
        qualification_type=certificate.type,
        overview=overview,
        difficulty=certificate.difficulty,
        related_tools=certificate.tool_or_lang,
        target_jobs=certificate.target_jobs,
        eligibility=None,
        exam_subjects=None,
        bonus_benefits=None,
    )


def build_local_details(match: CertificateMatch) -> CertificateDetails:
    return _trusted_details(
        match.certificate,
        match.matched_name,
        match.certificate.description,
    )


def generate_details_with_gemini(
    match: CertificateMatch, api_key: str, model: str = "gemini-2.5-flash"
) -> CertificateDetails:
    try:
        from google import genai
        from google.genai import types
        from google.genai.errors import APIError
    except ImportError as exc:
        raise RuntimeError(
            "Gemini 라이브러리가 설치되지 않았습니다. "
            "프로젝트 가상환경에서 pip install -r requirements.txt를 실행하세요."
        ) from exc

    client = genai.Client(api_key=api_key)
    source = match.certificate.model_dump()
    prompt = (
        "한국어 자격증 안내 도우미로서 아래 단일 JSON 레코드만 근거로 "
        "자격증 상세 정보를 구조화해 주세요. "
        "이름, 분야, 종류, 난이도, 관련 기술, 관련 직무는 레코드의 값을 그대로 사용하세요. "
        "overview는 description의 의미를 유지해 자연스럽게 정리할 수 있습니다. "
        "응시 조건, 시험 과목, 가산점/혜택은 레코드에 근거가 없으므로 반드시 null로 두세요. "
        "외부 지식으로 빈 정보를 채우거나 사실을 추측하지 마세요.\n"
        f"사용자가 찾은 이름: {match.matched_name}\n"
        f"레코드: {json.dumps(source, ensure_ascii=False)}"
    )

    # Gemini API가 거부하는 additionalProperties가 없는 안전한 Schema 정의
    certificate_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id": types.Schema(type=types.Type.STRING),
            "name": types.Schema(type=types.Type.STRING),
            "category": types.Schema(type=types.Type.STRING),
            "qualification_type": types.Schema(type=types.Type.STRING),
            "overview": types.Schema(type=types.Type.STRING),
            "difficulty": types.Schema(type=types.Type.STRING),
            "related_tools": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(type=types.Type.STRING),
            ),
            "target_jobs": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(type=types.Type.STRING),
            ),
            "eligibility": types.Schema(type=types.Type.STRING, nullable=True),
            "exam_subjects": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(type=types.Type.STRING),
                nullable=True,
            ),
            "bonus_benefits": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(type=types.Type.STRING),
                nullable=True,
            ),
        },
        required=["id", "name", "category", "qualification_type", "overview", "difficulty"],
    )

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=certificate_schema,
                temperature=0,
            ),
        )
    except APIError as exc:
        raise RuntimeError(f"Gemini API 요청에 실패했습니다: {exc}") from exc

    if not response.text:
        raise RuntimeError("Gemini에서 구조화된 응답을 받지 못했습니다.")

    try:
        parsed = json.loads(response.text)
        generated = CertificateDetails.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise RuntimeError(f"Gemini 응답 검증에 실패했습니다: {exc}") from exc

    if generated.id != match.certificate.id or generated.name != match.matched_name:
        raise RuntimeError("Gemini 응답의 자격증 식별 정보가 검색 결과와 일치하지 않습니다.")

    return _trusted_details(
        match.certificate,
        match.matched_name,
        generated.overview,
    )