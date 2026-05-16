"""Pydantic boundary for Groq trusted-sources JSON (domain allowlist)"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

from config.settings import (
    TRUSTED_SOURCES_DOMAIN_COUNT_MAX,
)


def _normalize_domain(raw: str) -> str:
    s = raw.strip().lower().rstrip(".")
    if s.startswith("www."):
        s = s[4:]
    return s


def _looks_like_domain(s: str) -> bool:
    if not s or "/" in s or ":" in s or " " in s or ".." in s:
        return False
    if "." not in s:
        return False
    parts = s.split(".")
    return all(parts) and all(p.replace("-", "").isalnum() for p in parts)


def _candidate_domain(raw: object) -> str | None:
    if isinstance(raw, str):
        s = raw.strip()
    elif raw is None:
        return None
    else:
        s = str(raw).strip()
    if not s:
        return None

    if s.startswith("//"):
        s = "https:" + s
    if "://" in s:
        parsed = urlparse(s)
        if parsed.hostname:
            norm = _normalize_domain(parsed.hostname)
            return norm if _looks_like_domain(norm) else None
        return None

    host_part = s.split("/")[0]
    host_part = host_part.split("?")[0]
    if ":" in host_part:
        host_part = host_part.rsplit(":", 1)[0]

    norm = _normalize_domain(host_part)
    return norm if _looks_like_domain(norm) else None


def _sanitize_domain_list(items: list[Any]) -> list[str]:
    """Extract apex domains, skip junk, dedupe, cap at max count."""

    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        cand = _candidate_domain(item)
        if cand is None or cand in seen:
            continue
        seen.add(cand)
        out.append(cand)
        if len(out) >= TRUSTED_SOURCES_DOMAIN_COUNT_MAX:
            break
    return out


class TrustedSourcesResponse(BaseModel):
    """LLM returns a JSON array; values are coerced and capped at the boundary."""

    domains: list[str] = Field(
        max_length=TRUSTED_SOURCES_DOMAIN_COUNT_MAX,
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_domains(cls, data: Any) -> Any:
        if isinstance(data, list):
            data = {"domains": data}
        if isinstance(data, dict):
            raw = data.get("domains")
            if isinstance(raw, list):
                merged = dict(data)
                merged["domains"] = _sanitize_domain_list(raw)
                return merged
        return data
