from __future__ import annotations

import os
from pathlib import Path
import sys

import streamlit as st
from dotenv import load_dotenv
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.web import cli as stcli

from rag_engine import (
    CertificateDetails,
    CertificateNotFoundError,
    build_local_details,
    generate_details_with_gemini,
    load_certificates,
    retrieve_certificate,
)


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def _show_list(items: list[str] | None) -> None:
    if items:
        st.markdown("\n".join(f"- {item}" for item in items))
    else:
        st.caption("현재 데이터셋에 해당 정보가 없습니다.")


def _render_details(details: CertificateDetails) -> None:
    st.subheader("자격증 상세 정보")
    st.markdown(f"### {details.name}")
    st.caption(
        f"{details.category} · {details.qualification_type} · 난이도 {details.difficulty}"
    )
    st.write(details.overview)

    left, right = st.columns(2)
    with left:
        st.markdown("**응시 조건**")
        st.write(details.eligibility or "현재 데이터셋에 해당 정보가 없습니다.")
        st.markdown("**시험 과목**")
        _show_list(details.exam_subjects)
        st.markdown("**가산점·혜택**")
        _show_list(details.bonus_benefits)
    with right:
        st.markdown("**관련 기술·도구**")
        _show_list(details.related_tools)
        st.markdown("**관련 직무**")
        _show_list(details.target_jobs)

    st.info(
        "응시 조건, 시험 과목, 가산점 정보는 현재 데이터셋에 없습니다. "
        "최신 세부 내용은 공식 시행기관에서 확인해 주세요."
    )


def main() -> None:
    st.set_page_config(page_title="자격증 상세 정보 | Certi Mentor", page_icon="🎓")
    st.title("🎓 Certi Mentor")
    st.write("궁금한 자격증을 입력하면 데이터셋을 바탕으로 상세 정보를 정리해 드립니다.")

    try:
        certificates = load_certificates()
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()

    with st.form("certificate_prompt"):
        query = st.text_input(
            "무엇이 궁금하신가요?",
            placeholder="정보시스템 감리자 자격증에 대해 설명해줘",
        )
        submitted = st.form_submit_button("자격증 상세 정보 보기", type="primary")

    api_key = st.sidebar.text_input(
        "Gemini API Key",
        value=os.getenv("GEMINI_API_KEY", ""),
        type="password",
        help=".env 파일에 GEMINI_API_KEY를 저장하거나 여기에 입력할 수 있습니다.",
    )
    st.sidebar.caption(f"데이터셋 자격증 {len(certificates)}개")

    if not submitted:
        return
    if not query.strip():
        st.warning("자격증 이름이나 질문을 입력해 주세요.")
        return

    try:
        match = retrieve_certificate(query, certificates)
        if api_key.strip():
            details = generate_details_with_gemini(
                match,
                api_key.strip(),
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            )
            st.caption("Gemini Structured Output으로 정보를 정리했습니다.")
        else:
            details = build_local_details(match)
            st.caption("API 키 없이 데이터셋 검색 결과를 표시합니다.")
    except CertificateNotFoundError as exc:
        st.warning(str(exc))
        return
    except (RuntimeError, ValueError) as exc:
        st.error(f"자격증 정보를 불러오지 못했습니다: {exc}")
        return

    _render_details(details)


if __name__ == "__main__":
    if get_script_run_ctx(suppress_warning=True) is None:
        sys.argv = [
            "streamlit",
            "run",
            str(Path(__file__).resolve()),
            *sys.argv[1:],
        ]
        stcli.main()
    else:
        main()
