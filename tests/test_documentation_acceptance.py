from pathlib import Path


def test_backend_architecture_document_is_current() -> None:
    doc = Path("docs/architecture/backend-refactor.md")

    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    for required in [
        "api.main:create_app",
        "RequestIDMiddleware",
        "services/kb_service.py",
        "services/search_service.py",
        "require_kb_owner",
        "require_chat_session_owner",
    ]:
        assert required in text


def test_api_contract_document_lists_canonical_routes() -> None:
    doc = Path("docs/architecture/api-contract.md")

    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    for route in [
        "/api/auth/login",
        "/api/knowledge_bases/{kb_id}",
        "/api/upload/{knowledge_base_id}",
        "/api/jobs/{job_id}",
        "/api/search/{knowledge_base_id}",
        "/api/chat/sessions/{session_id}",
        "/api/ppt/chat",
        "/api/health/dependencies",
    ]:
        assert route in text


def test_readme_documents_developer_workflow() -> None:
    readme = Path("README.md")

    assert readme.exists()
    text = readme.read_text(encoding="utf-8")
    for required in [
        "python -m uvicorn api.main:create_app --factory",
        "pytest -q",
        "npm run build",
    ]:
        assert required in text


def test_windows_launcher_uses_refactored_app_factory() -> None:
    launcher = Path("start_web.bat").read_text(encoding="utf-8")

    assert "api.main:create_app --factory" in launcher
