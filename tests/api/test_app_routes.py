from api.main import create_app


def test_create_app_registers_required_route_prefixes():
    app = create_app()
    paths = {route.path for route in app.routes}

    required_prefixes = [
        "/api/auth",
        "/api/knowledge_bases",
        "/api/upload",
        "/api/jobs",
        "/api/documents",
        "/api/search",
        "/api/chat",
        "/api/ppt",
        "/api/health",
    ]

    for prefix in required_prefixes:
        assert any(path.startswith(prefix) for path in paths), prefix


def test_create_app_does_not_require_running_external_services_on_import():
    app = create_app()

    assert app.title
    assert len(app.routes) > 0
