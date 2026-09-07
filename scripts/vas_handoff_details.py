"""Render optional handoff fields without losing the form's selections."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prompt_details(document: dict) -> str:
    from vas_ai_contract import clean
    context = document.get("context") or {}
    details = (context.get("requirements") or {}).get("value") or {}
    keys = ("reference", "capabilities", "dataReadiness", "platforms", "deadline", "budget", "attachments")
    selected = {key: details[key] for key in keys if key in details}
    sections = ["추가 요구사항(JSON):\n" + clean(json.dumps(selected, ensure_ascii=False, indent=2), 8000)]
    attachments = details.get("attachments") or {}
    if attachments.get("files"):
        sections.append("참고 파일 원본을 코딩 AI에 별도로 첨부하세요. VAS는 파일 내용을 전송하지 않았습니다. AI는 받지 않은 내용을 추정하지 마세요.")
    design = context.get("design") or {}
    if design.get("included") and design.get("tokens"):
        sections.append("확정 디자인 토큰(JSON):\n" + clean(json.dumps(design["tokens"], ensure_ascii=False, indent=2), 4000))
    resource = ROOT / ".agents/agent-resources.json"
    if resource.is_file():
        workflow = json.loads(resource.read_text(encoding="utf-8"))["workflow"]
    else:
        workflow = "주 실행자가 원본을 확인하고 구현·검증을 완료하세요. 실제 호출 도구가 제공될 때만 필요한 역할에 위임하세요."
    sections.append("에이전트 작업 방식:\n" + workflow)
    return "\n\n".join(sections)
