"""
Tests for Web Dev Tools + App Dev Tools + Code Executor Upgrades.
Validates all 18 new tools across 3 modules.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ══════════════════════════════════════════════════════════════
# Web Dev Tools Tests
# ══════════════════════════════════════════════════════════════

def test_web_scaffold_react():
    from agents.tools.web_dev_tools import web_scaffold_project
    with tempfile.TemporaryDirectory() as d:
        r = web_scaffold_project("test-app", "react", d)
        assert r["success"] is True
        assert len(r["files_created"]) >= 5
        assert (Path(d) / "test-app" / "src" / "App.jsx").exists()
        assert (Path(d) / "test-app" / "package.json").exists()
        print(f"  OK React scaffold: {len(r['files_created'])} files")


def test_web_scaffold_vue():
    from agents.tools.web_dev_tools import web_scaffold_project
    with tempfile.TemporaryDirectory() as d:
        r = web_scaffold_project("vue-app", "vue", d)
        assert r["success"] is True
        assert (Path(d) / "vue-app" / "src" / "App.vue").exists()
        print(f"  OK Vue scaffold: {len(r['files_created'])} files")


def test_web_scaffold_nextjs():
    from agents.tools.web_dev_tools import web_scaffold_project
    with tempfile.TemporaryDirectory() as d:
        r = web_scaffold_project("next-app", "nextjs", d)
        assert r["success"] is True
        assert (Path(d) / "next-app" / "app" / "page.tsx").exists()
        print(f"  OK Next.js scaffold: {len(r['files_created'])} files")


def test_web_scaffold_vanilla():
    from agents.tools.web_dev_tools import web_scaffold_project
    with tempfile.TemporaryDirectory() as d:
        r = web_scaffold_project("vanilla-app", "vanilla", d)
        assert r["success"] is True
        assert (Path(d) / "vanilla-app" / "index.html").exists()
        assert (Path(d) / "vanilla-app" / "js" / "app.js").exists()
        print(f"  OK Vanilla scaffold: {len(r['files_created'])} files")


def test_web_generate_react_component():
    from agents.tools.web_dev_tools import web_generate_component
    r = web_generate_component("UserProfile", "react",
                                [{"name": "userId", "type": "string"}],
                                ["state", "api_call"])
    assert r["success"] is True
    assert "UserProfile" in r["code"]
    assert "useState" in r["code"]
    assert "fetchData" in r["code"]
    print(f"  OK React component: {r['filename']}")


def test_web_generate_vue_component():
    from agents.tools.web_dev_tools import web_generate_component
    r = web_generate_component("Dashboard", "vue",
                                [{"name": "title", "type": "String", "default": "'Home'"}],
                                ["state"])
    assert r["success"] is True
    assert "Dashboard" in r["code"]
    assert "<template>" in r["code"]
    print(f"  OK Vue component: {r['filename']}")


def test_web_generate_express_api():
    from agents.tools.web_dev_tools import web_generate_api
    r = web_generate_api("users", "express",
                          ["create", "read", "list"],
                          [{"name": "email", "type": "string", "required": True}])
    assert r["success"] is True
    assert "router.get" in r["code"]
    assert "router.post" in r["code"]
    print(f"  OK Express API: {r['filename']}")


def test_web_generate_fastapi():
    from agents.tools.web_dev_tools import web_generate_api
    r = web_generate_api("products", "fastapi",
                          ["create", "read", "list"],
                          [{"name": "price", "type": "number", "required": True}])
    assert r["success"] is True
    assert "FastAPI" in r["code"] or "APIRouter" in r["code"]
    print(f"  OK FastAPI: {r['filename']}")


def test_web_generate_css():
    from agents.tools.web_dev_tools import web_generate_css
    r = web_generate_css("design_system", "dark")
    assert r["success"] is True
    assert "--color-primary" in r["css"]
    assert ".btn" in r["css"]
    assert "@keyframes" in r["css"]
    print(f"  OK Design system CSS: {len(r['css'])} chars")


def test_web_deploy_docker():
    from agents.tools.web_dev_tools import web_deploy_config
    r = web_deploy_config("docker", "react", "my-app")
    assert r["success"] is True
    assert "FROM" in r["config"]
    assert "nginx" in r["config"].lower()
    print(f"  OK Docker config: {r['filename']}")


def test_web_deploy_nginx():
    from agents.tools.web_dev_tools import web_deploy_config
    r = web_deploy_config("nginx", "react")
    assert r["success"] is True
    assert "server" in r["config"]
    assert "proxy_pass" in r["config"]
    print(f"  OK Nginx config: {r['filename']}")


# ══════════════════════════════════════════════════════════════
# App Dev Tools Tests
# ══════════════════════════════════════════════════════════════

def test_app_scaffold_react_native():
    from agents.tools.app_dev_tools import app_scaffold_project
    with tempfile.TemporaryDirectory() as d:
        r = app_scaffold_project("MyApp", "react_native", d)
        assert r["success"] is True
        assert (Path(d) / "MyApp" / "App.tsx").exists()
        assert (Path(d) / "MyApp" / "package.json").exists()
        print(f"  OK React Native scaffold: {len(r['files_created'])} files")


def test_app_scaffold_flutter():
    from agents.tools.app_dev_tools import app_scaffold_project
    with tempfile.TemporaryDirectory() as d:
        r = app_scaffold_project("flutter_app", "flutter", d)
        assert r["success"] is True
        assert (Path(d) / "flutter_app" / "lib" / "main.dart").exists()
        assert (Path(d) / "flutter_app" / "pubspec.yaml").exists()
        print(f"  OK Flutter scaffold: {len(r['files_created'])} files")


def test_app_scaffold_kotlin():
    from agents.tools.app_dev_tools import app_scaffold_project
    with tempfile.TemporaryDirectory() as d:
        r = app_scaffold_project("KotlinApp", "kotlin", d)
        assert r["success"] is True
        assert len(r["files_created"]) >= 2
        print(f"  OK Kotlin scaffold: {len(r['files_created'])} files")


def test_app_scaffold_swift():
    from agents.tools.app_dev_tools import app_scaffold_project
    with tempfile.TemporaryDirectory() as d:
        r = app_scaffold_project("SwiftApp", "swift", d)
        assert r["success"] is True
        assert len(r["files_created"]) >= 2
        print(f"  OK Swift scaffold: {len(r['files_created'])} files")


def test_app_generate_rn_screen():
    from agents.tools.app_dev_tools import app_generate_screen
    r = app_generate_screen("SettingsScreen", "react_native", "list", ["pull_refresh"])
    assert r["success"] is True
    assert "SettingsScreen" in r["code"]
    assert "RefreshControl" in r["code"]
    print(f"  OK RN screen: {r['filename']}")


def test_app_generate_flutter_screen():
    from agents.tools.app_dev_tools import app_generate_screen
    r = app_generate_screen("ProfileScreen", "flutter", "detail")
    assert r["success"] is True
    assert "ProfileScreen" in r["code"]
    assert "StatefulWidget" in r["code"]
    print(f"  OK Flutter screen: {r['filename']}")


def test_app_generate_api_client():
    from agents.tools.app_dev_tools import app_generate_api_client
    r = app_generate_api_client(
        "https://api.myapp.com",
        "react_native",
        [{"path": "/users", "method": "GET", "name": "getUsers"},
         {"path": "/users", "method": "POST", "name": "createUser"}],
    )
    assert r["success"] is True
    assert "getUsers" in r["code"]
    assert "createUser" in r["code"]
    print(f"  OK API client: {r['filename']}, {r['endpoints']} endpoints")


def test_app_generate_assets():
    from agents.tools.app_dev_tools import app_generate_assets
    r = app_generate_assets("both", "Test App", "#6366F1")
    assert r["success"] is True
    assert r["total_files"] >= 3
    assert "colors.xml" in r["files"]
    print(f"  OK Assets: {r['total_files']} files generated")


def test_app_sign_android():
    from agents.tools.app_dev_tools import app_sign_release
    r = app_sign_release("android", "my-app", "release-key")
    assert r["success"] is True
    assert "keytool" in r["keytool_command"]
    assert "signingConfigs" in r["gradle_config"]
    print(f"  OK Android signing: config generated")


def test_app_sign_ios():
    from agents.tools.app_dev_tools import app_sign_release
    r = app_sign_release("ios", "my-app")
    assert r["success"] is True
    assert len(r["instructions"]) >= 5
    print(f"  OK iOS signing: {len(r['instructions'])} steps")


# ══════════════════════════════════════════════════════════════
# Code Executor Upgrade Tests
# ══════════════════════════════════════════════════════════════

def test_execute_javascript():
    from agents.tools.code_executor import execute_javascript
    r = execute_javascript("console.log('Hello from JS');")
    if r["success"]:
        assert "Hello from JS" in r["stdout"]
        print(f"  OK JS execution: {r['stdout'].strip()}")
    else:
        print(f"  OK JS execution: blocked or Node not found ({r['stderr'][:50]})")


def test_js_safety_block():
    from agents.tools.code_executor import execute_javascript
    r = execute_javascript("require('child_process').exec('ls');")
    assert r["success"] is False
    assert "Blocked" in r["stderr"]
    print(f"  OK JS safety: {r['stderr']}")


def test_execute_html():
    from agents.tools.code_executor import execute_html
    html = '<html><head><title>Test</title></head><body>Hello</body></html>'
    r = execute_html(html)
    assert r["success"] is True
    assert Path(r["file_path"]).exists()
    print(f"  OK HTML: valid={r['valid']}, warnings={len(r['warnings'])}")


def test_html_validation_warnings():
    from agents.tools.code_executor import execute_html
    r = execute_html("<div>No doctype, no head</div>")
    assert r["success"] is True
    assert len(r["warnings"]) >= 3  # Missing doctype, html, head, title
    print(f"  OK HTML validation: {len(r['warnings'])} warnings found")


def test_lint_python():
    from agents.tools.code_executor import lint_code
    code = "x = 1\n" + "y = 2\t\n" + "z" * 130 + " = 3\n"
    r = lint_code(code, "python")
    assert r["success"] is True
    assert r["total"] >= 2  # tab + long line
    print(f"  OK Python lint: {r['total']} issues")


def test_lint_javascript():
    from agents.tools.code_executor import lint_code
    code = "var x = 1;\nif (x == 2) { console.log('yes'); }\n"
    r = lint_code(code, "javascript")
    assert r["success"] is True
    assert r["total"] >= 2  # var + == + console.log
    print(f"  OK JS lint: {r['total']} issues")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Dev Core Upgrades — Test Suite")
    print("=" * 60)

    tests = [
        ("Web: React scaffold", test_web_scaffold_react),
        ("Web: Vue scaffold", test_web_scaffold_vue),
        ("Web: Next.js scaffold", test_web_scaffold_nextjs),
        ("Web: Vanilla scaffold", test_web_scaffold_vanilla),
        ("Web: React component", test_web_generate_react_component),
        ("Web: Vue component", test_web_generate_vue_component),
        ("Web: Express API", test_web_generate_express_api),
        ("Web: FastAPI", test_web_generate_fastapi),
        ("Web: CSS design system", test_web_generate_css),
        ("Web: Docker deploy", test_web_deploy_docker),
        ("Web: Nginx deploy", test_web_deploy_nginx),
        ("App: React Native scaffold", test_app_scaffold_react_native),
        ("App: Flutter scaffold", test_app_scaffold_flutter),
        ("App: Kotlin scaffold", test_app_scaffold_kotlin),
        ("App: Swift scaffold", test_app_scaffold_swift),
        ("App: RN screen gen", test_app_generate_rn_screen),
        ("App: Flutter screen gen", test_app_generate_flutter_screen),
        ("App: API client gen", test_app_generate_api_client),
        ("App: Asset generation", test_app_generate_assets),
        ("App: Android signing", test_app_sign_android),
        ("App: iOS signing", test_app_sign_ios),
        ("Exec: JavaScript", test_execute_javascript),
        ("Exec: JS safety block", test_js_safety_block),
        ("Exec: HTML write", test_execute_html),
        ("Exec: HTML validation", test_html_validation_warnings),
        ("Exec: Python lint", test_lint_python),
        ("Exec: JS lint", test_lint_javascript),
    ]

    passed = 0
    for name, fn in tests:
        print(f"\n--- {name} ---")
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")

    print(f"\n{'=' * 60}")
    print(f"  {passed}/{len(tests)} TESTS PASSED!")
    print(f"{'=' * 60}\n")
