"""VAS 드라이런 시나리오 데이터."""

SCENARIOS = [
    {
        "id": 1, "label": "경량 프론트엔드 (포모도로 타이머)",
        "input": {
            "projectName": "Pomodoro Timer",
            "projectPurpose": "Focus tool using 25-5 rule.",
            "keyFeatures": "Visual countdown, start/pause/reset.",
            "dataProvided": "No",
            "deployment": "Local HTML file",
            "deadline": "Tomorrow",
            "budget": "0",
            "otherRequests": "Neo-Brutalism design."
        },
        "expect_stack": "html",
        "expect_complexity": "lite",
        "expect_preset": "neobrutal",
        "expect_tester_bypass": True,
    },
    {
        "id": 2, "label": "풀스택 SaaS (프로젝트 관리 도구)",
        "input": {
            "projectName": "TaskFlow Pro",
            "projectPurpose": "Team project management SaaS.",
            "keyFeatures": "Kanban board, real-time sync, user auth.",
            "dataProvided": "Yes (PostgreSQL)",
            "deployment": "Cloud (AWS)",
            "deadline": "3 months",
            "budget": "5000000",
            "otherRequests": "Linear-style dark mode UI."
        },
        "expect_stack": "fullstack",
        "expect_complexity": "ultra",
        "expect_preset": "linear",
        "expect_tester_bypass": False,
    },
    {
        "id": 3, "label": "데이터 파이프라인 (의료 영상 분석)",
        "input": {
            "projectName": "MedScan AI",
            "projectPurpose": "X-ray image classification for diagnosis.",
            "keyFeatures": "Image upload, AI inference, report PDF.",
            "dataProvided": "Yes (DICOM images)",
            "deployment": "On-premise hospital server",
            "deadline": "6 months",
            "budget": "20000000",
            "otherRequests": "HIPAA compliance. Strict data security."
        },
        "expect_stack": "python",
        "expect_complexity": "ultra",
        "expect_preset": None,
        "expect_tester_bypass": False,
    },
    {
        "id": 4, "label": "모바일 우선 PWA (카페 주문 앱)",
        "input": {
            "projectName": "CafeOrder",
            "projectPurpose": "Mobile ordering for local cafe.",
            "keyFeatures": "Menu browsing, cart, QR payment.",
            "dataProvided": "No",
            "deployment": "PWA (mobile browser)",
            "deadline": "1 month",
            "budget": "500000",
            "otherRequests": "Apple HIG style. Glassmorphism."
        },
        "expect_stack": "frontend",
        "expect_complexity": "normal",
        "expect_preset": "apple",
        "expect_tester_bypass": False,
    },
    {
        "id": 5, "label": "CLI 유틸리티 (파일 변환기)",
        "input": {
            "projectName": "FileForge",
            "projectPurpose": "Batch convert CSV to JSON.",
            "keyFeatures": "CLI interface, glob patterns, progress bar.",
            "dataProvided": "No",
            "deployment": "Local terminal (pip install)",
            "deadline": "1 week",
            "budget": "0",
            "otherRequests": "No UI needed. Python only."
        },
        "expect_stack": "python",
        "expect_complexity": "lite",
        "expect_preset": None,
        "expect_tester_bypass": False,
    },
    {
        "id": 6, "label": "실시간 대시보드 (IoT 센서 모니터링)",
        "input": {
            "projectName": "SensorHub",
            "projectPurpose": "Real-time IoT sensor dashboard.",
            "keyFeatures": "WebSocket live graphs, alerts, CSV export.",
            "dataProvided": "Yes (MQTT stream)",
            "deployment": "Synology NAS Docker",
            "deadline": "2 months",
            "budget": "1000000",
            "otherRequests": "Glow UI dark theme. Futuristic."
        },
        "expect_stack": "fullstack",
        "expect_complexity": "normal",
        "expect_preset": "glow",
        "expect_tester_bypass": False,
    },
    {
        "id": 7, "label": "단일 랜딩 페이지 (포트폴리오)",
        "input": {
            "projectName": "Portfolio 2026",
            "projectPurpose": "Personal portfolio website.",
            "keyFeatures": "Hero section, project gallery, contact form.",
            "dataProvided": "No",
            "deployment": "GitHub Pages",
            "deadline": "3 days",
            "budget": "0",
            "otherRequests": "Awwwards-level editorial design."
        },
        "expect_stack": "html",
        "expect_complexity": "lite",
        "expect_preset": "awwwards",
        "expect_tester_bypass": True,
    },
    {
        "id": 8, "label": "엔터프라이즈 어드민 (ERP 백오피스)",
        "input": {
            "projectName": "BizAdmin",
            "projectPurpose": "Internal ERP admin panel.",
            "keyFeatures": "CRUD tables, role management, audit log.",
            "dataProvided": "Yes (MySQL)",
            "deployment": "Internal network",
            "deadline": "4 months",
            "budget": "8000000",
            "otherRequests": "Ant Design style. Data-heavy tables."
        },
        "expect_stack": "fullstack",
        "expect_complexity": "ultra",
        "expect_preset": "ant",
        "expect_tester_bypass": False,
    },
    {
        "id": 9, "label": "음성 인식 보안 앱 (출입 관리)",
        "input": {
            "projectName": "VoiceGate",
            "projectPurpose": "Voice-based access control system.",
            "keyFeatures": "Voice recording, speaker verification, door API.",
            "dataProvided": "Yes (voice samples)",
            "deployment": "Raspberry Pi edge device",
            "deadline": "5 months",
            "budget": "15000000",
            "otherRequests": "Strict privacy. Audio data must be purged after use."
        },
        "expect_stack": "python",
        "expect_complexity": "ultra",
        "expect_preset": None,
        "expect_tester_bypass": False,
    },
    {
        "id": 10, "label": "Stripe 결제 연동 (구독 서비스)",
        "input": {
            "projectName": "SubPay",
            "projectPurpose": "Subscription billing management.",
            "keyFeatures": "Stripe checkout, invoice PDF, webhook handler.",
            "dataProvided": "No",
            "deployment": "Vercel + Supabase",
            "deadline": "6 weeks",
            "budget": "2000000",
            "otherRequests": "Stripe-style clean fintech look."
        },
        "expect_stack": "fullstack",
        "expect_complexity": "normal",
        "expect_preset": "stripe",
        "expect_tester_bypass": False,
    },
]
