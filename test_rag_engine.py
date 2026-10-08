import unittest
from pathlib import Path

from rag_engine import (
    build_local_details,
    load_certificates,
    retrieve_certificate,
)


class RagEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.certificates = load_certificates(
            Path(__file__).resolve().parent / "data" / "cert_data.json"
        )

    def test_retrieves_certificate_from_natural_language_prompt(self) -> None:
        match = retrieve_certificate(
            "정보시스템 감리자 자격증에 대해 설명해줘", self.certificates
        )
        self.assertEqual(match.certificate.id, "cert_004")
        self.assertEqual(match.matched_name, "정보시스템감리사")

    def test_retrieves_requested_alias(self) -> None:
        match = retrieve_certificate("SQLP 자격증 알려줘", self.certificates)
        self.assertEqual(match.matched_name, "SQLP")

    def test_unknown_exam_details_are_not_invented(self) -> None:
        match = retrieve_certificate("정보시스템감리사", self.certificates)
        details = build_local_details(match)
        self.assertIsNone(details.eligibility)
        self.assertIsNone(details.exam_subjects)
        self.assertIsNone(details.bonus_benefits)


if __name__ == "__main__":
    unittest.main()
