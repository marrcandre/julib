"""Shared limits and normalization for bibliographic metadata fields."""

from typing import Any

from django.core.exceptions import ValidationError

SUBTITLE_MAX_LENGTH = 500
DESCRIPTION_MAX_LENGTH = 20_000
SUBJECTS_MAX_ITEMS = 50
SUBJECT_MAX_LENGTH = 200


def normalize_subjects(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    subjects: list[str] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, dict):
            item = item.get("name")
        if not isinstance(item, str):
            return []
        subject = " ".join(item.split())
        if not subject:
            continue
        if len(subject) > SUBJECT_MAX_LENGTH:
            return []
        key = subject.casefold()
        if key not in seen:
            subjects.append(subject)
            seen.add(key)
            if len(subjects) > SUBJECTS_MAX_ITEMS:
                return []
    return subjects


def validate_subjects(value: Any) -> None:
    if not isinstance(value, list):
        raise ValidationError("Assuntos devem ser uma lista de textos.")
    if len(value) > SUBJECTS_MAX_ITEMS:
        raise ValidationError(f"Informe no máximo {SUBJECTS_MAX_ITEMS} assuntos.")
    if any(not isinstance(item, str) for item in value):
        raise ValidationError("Cada assunto deve ser um texto.")
    if any(len(item) > SUBJECT_MAX_LENGTH for item in value):
        raise ValidationError(f"Cada assunto deve ter no máximo {SUBJECT_MAX_LENGTH} caracteres.")
