"""Design sample metadata; URLs do not prove a visual reference was inspected."""
from __future__ import annotations

import json
import re

SAMPLE_KEYS = {"bento", "aurora", "clay", "noir", "botanical", "retro", "swiss", "cyber", "kinetic", "collage", "awwwards", "linear", "stripe", "notion"}
REPOSITORY = "https://github.com/zmsqnfl-commits/quintpact-vas"
SAMPLES = "https://zmsqnfl-commits.github.io/quintpact-vas/src/design-sample.html"
INSTRUCTIONS = "\n".join([
    "샘플은 기본 스타일의 구도 참고용입니다. 사용자 수정이 있으면 샘플과 달라도 확정 디자인 토큰을 따르세요.",
    "샘플의 문구·사진·사업 데이터는 구현 요구사항이 아닙니다. 지정한 디자인 적용 범위만 변경하세요.",
    "버전 소스는 지정한 릴리스 태그의 파일입니다. 실행 샘플은 최신 Pages이며 해당 버전과 일치하는지는 확인되지 않았습니다.",
    "링크 전달은 시각 참조 확인이 아닙니다. 열지 못하거나 버전을 대조하지 못하면 시각 참조 미확인으로 보고하세요.",
    "fontFamily는 확정 토큰의 글꼴 이름이며 파일 제공을 뜻하지 않습니다. 필요한 로컬 자산·사용 조건은 버전 소스에서 직접 확인하세요. 외부 CDN·원격 폰트를 추가하지 마세요.",
])


def reference(design, scope, version):
    if not isinstance(design, dict) or design.get("included") is not True or not isinstance(scope, dict) or scope.get("mode") == "preserve":
        return None
    key = design.get("basePreset") or ("" if design.get("preset") == "custom" else design.get("preset"))
    known = isinstance(key, str) and key in SAMPLE_KEYS
    valid_version = isinstance(version, str) and bool(re.fullmatch(r"\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?", version))
    tag = "v" + version if valid_version else None
    return {
        "status": "unverified", "sampleKind": "base-preset", "samplePreset": key if known else None,
        "userModified": design.get("preset") == "custom", "valueAuthority": "confirmed-design-tokens",
        "applicationScope": {"mode": scope.get("mode"), "scope": scope.get("scope") or ""},
        "vasVersion": version if valid_version else None, "sourceRef": tag,
        "versionedSourceUrl": f"{REPOSITORY}/blob/{tag}/src/design-sample.html" if known and tag else None,
        "liveSampleUrl": f"{SAMPLES}?preset={key}" if known else None,
        "liveSampleVersion": "not-verified",
    }


def attach(document):
    context = document.get("context") or {}
    design = context.get("design")
    scope = (document.get("task") or {}).get("designScope")
    if isinstance(scope, dict) and scope.get("mode") == "preserve":
        context["design"] = {"included": False}
        return document
    if not isinstance(design, dict) or design.get("included") is not True:
        return document
    value = reference(design, scope, (document.get("generatedBy") or {}).get("version"))
    if value:
        design["visualReference"] = value
    return document


def prompt(document):
    design = (document.get("context") or {}).get("design") or {}
    scope = (document.get("task") or {}).get("designScope") or {}
    if design.get("included") is not True or scope.get("mode") == "preserve" or not design.get("visualReference"):
        return ""
    value = design["visualReference"]
    text = "디자인 시각 참조 (미확인):\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n" + INSTRUCTIONS
    if not value.get("samplePreset"):
        text += "\n이 스타일의 공개 샘플은 없습니다. 다른 스타일의 샘플로 대체하지 말고 확정 토큰을 기준으로 구현하세요."
    return text + "\n\n"
