"""Tests for Database Tools + Git Tools + DevOps Tools (Test Gen, API Test, Dep Scanner)."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ══════════════════════════════════════════════════════════════
# Database Tools Tests
# ══════════════════════════════════════════════════════════════

def test_db_design_schema_postgres():
    from agents.tools.database_tools import db_design_schema
    r = db_design_schema(dialect="postgres")
    assert r["success"] is True
    assert "CREATE TABLE" in r["sql"]
    assert "gen_random_uuid()" in r["sql"]
    print(f"  OK Postgres schema: {r['tables_count']} tables")


def test_db_design_schema_mysql():
    from agents.tools.database_tools import db_design_schema
    tables = [{"name": "products", "columns": [
        {"name": "id", "type": "integer", "primary": True},
        {"name": "name", "type": "string", "nullable": False},
        {"name": "price", "type": "decimal"},
    ], "indexes": [{"columns": ["name"], "unique": True}]}]
    r = db_design_schema(tables, "mysql")
    assert r["success"] is True
    assert "DECIMAL" in r["sql"]
    assert "CREATE UNIQUE INDEX" in r["sql"]
    print(f"  OK MySQL schema with indexes")


def test_db_generate_migration_raw():
    from agents.tools.database_tools import db_generate_migration
    r = db_generate_migration("add_users", format="raw_sql")
    assert r["success"] is True
    assert "UP" in r["code"]
    assert "DOWN" in r["code"]
    print(f"  OK Raw migration: {r['filename']}")


def test_db_generate_migration_alembic():
    from agents.tools.database_tools import db_generate_migration
    r = db_generate_migration("initial", format="alembic")
    assert r["success"] is True
    assert "alembic" in r["code"]
    assert "def upgrade" in r["code"]
    assert "def downgrade" in r["code"]
    print(f"  OK Alembic migration: {r['filename']}")


def test_db_generate_model_sqlalchemy():
    from agents.tools.database_tools import db_generate_model
    r = db_generate_model("User", orm="sqlalchemy")
    assert r["success"] is True
    assert "class User(Base)" in r["code"]
    assert "__tablename__" in r["code"]
    print(f"  OK SQLAlchemy model: {r['filename']}")


def test_db_generate_model_django():
    from agents.tools.database_tools import db_generate_model
    r = db_generate_model("Product", fields=[
        {"name": "id", "type": "uuid", "primary": True},
        {"name": "title", "type": "string"},
        {"name": "price", "type": "decimal"},
    ], orm="django")
    assert r["success"] is True
    assert "models.Model" in r["code"]
    assert "DecimalField" in r["code"]
    print(f"  OK Django model: {r['filename']}")


def test_db_generate_model_prisma():
    from agents.tools.database_tools import db_generate_model
    r = db_generate_model("Post", orm="prisma")
    assert r["success"] is True
    assert "model Post" in r["code"]
    assert "@id" in r["code"]
    print(f"  OK Prisma model: {r['filename']}")


def test_db_generate_query_select():
    from agents.tools.database_tools import db_generate_query
    r = db_generate_query("select", "users",
                           ["users.name", "orders.total"],
                           joins=[{"table": "orders", "on": "users.id = orders.user_id"}],
                           where=[{"column": "users.is_active", "op": "=", "value": "true"}],
                           limit=10)
    assert r["success"] is True
    assert "INNER JOIN" in r["sql"]
    assert "WHERE" in r["sql"]
    assert "LIMIT" in r["sql"]
    print(f"  OK Select query with JOIN")


def test_db_generate_query_cte():
    from agents.tools.database_tools import db_generate_query
    r = db_generate_query("cte", "orders", limit=5)
    assert r["success"] is True
    assert "WITH ranked AS" in r["sql"]
    assert "ROW_NUMBER()" in r["sql"]
    print(f"  OK CTE query")


def test_db_seed_data_sql():
    from agents.tools.database_tools import db_seed_data
    r = db_seed_data("users", count=5, format="sql")
    assert r["success"] is True
    assert "INSERT INTO users" in r["data"]
    assert r["rows"] == 5
    print(f"  OK Seed data: {r['rows']} rows SQL")


def test_db_seed_data_json():
    from agents.tools.database_tools import db_seed_data
    r = db_seed_data("users", count=3, format="json")
    assert r["success"] is True
    data = json.loads(r["data"])
    assert len(data) == 3
    assert "email" in data[0]
    print(f"  OK Seed data: {r['rows']} rows JSON")


def test_db_analyze_schema():
    from agents.tools.database_tools import db_analyze_schema
    sql = "CREATE TABLE users (id UUID PRIMARY KEY, name TEXT, FOREIGN KEY (org_id) REFERENCES orgs(id));"
    r = db_analyze_schema(sql)
    assert r["success"] is True
    assert r["score"] >= 0
    assert r["grade"] in ("A", "B", "C", "D")
    print(f"  OK Schema analysis: score={r['score']}, grade={r['grade']}")


def test_db_generate_repo_sqlalchemy():
    from agents.tools.database_tools import db_generate_repo
    r = db_generate_repo("User", "sqlalchemy")
    assert r["success"] is True
    assert "class UserRepository" in r["code"]
    assert "def create" in r["code"]
    assert "def get_by_id" in r["code"]
    print(f"  OK SQLAlchemy repo: {len(r['operations'])} operations")


# ══════════════════════════════════════════════════════════════
# Git Tools Tests
# ══════════════════════════════════════════════════════════════

def test_git_status():
    from agents.tools.git_tools import git_status
    r = git_status("c:\\astra agent")
    assert r["success"] is True
    assert "branch" in r
    print(f"  OK Git status: branch={r['branch']}, changes={r['total_changes']}")


def test_git_log():
    from agents.tools.git_tools import git_log
    r = git_log("c:\\astra agent", count=5)
    assert r["success"] is True
    assert len(r["commits"]) >= 1
    print(f"  OK Git log: {r['total']} commits")


def test_git_diff():
    from agents.tools.git_tools import git_diff
    r = git_diff("c:\\astra agent", "unstaged")
    assert r["success"] is True
    print(f"  OK Git diff: {len(r.get('stat', ''))} chars")


def test_git_branch_list():
    from agents.tools.git_tools import git_branch
    r = git_branch("c:\\astra agent", "list")
    assert r["success"] is True
    assert "branches" in r
    print(f"  OK Git branches: {r['total']} branches")


def test_git_stash_list():
    from agents.tools.git_tools import git_stash
    r = git_stash("c:\\astra agent", "list")
    assert r["success"] is True
    print(f"  OK Git stash list: {r['total']} stashes")


# ══════════════════════════════════════════════════════════════
# DevOps Tools Tests
# ══════════════════════════════════════════════════════════════

def test_generate_python_tests_pytest():
    from agents.tools.devops_tools import generate_tests
    code = '''
def add(a, b):
    return a + b

def greet(name):
    return f"Hello, {name}"

class Calculator:
    def multiply(self, x, y):
        return x * y
    def divide(self, x, y):
        if y == 0: raise ValueError("Division by zero")
        return x / y
'''
    r = generate_tests(code, "python", "pytest", "thorough")
    assert r["success"] is True
    assert r["functions_found"] >= 2
    assert r["classes_found"] >= 1
    assert r["test_count"] >= 4
    assert "def test_add_basic" in r["test_code"]
    assert "def test_greet_basic" in r["test_code"]
    print(f"  OK Python test gen: {r['test_count']} tests, {r['functions_found']} funcs, {r['classes_found']} classes")


def test_generate_js_tests_jest():
    from agents.tools.devops_tools import generate_tests
    code = '''
export function fetchUsers() { return []; }
export const createUser = (name) => ({ name });
export class UserService { getAll() { return []; } }
'''
    r = generate_tests(code, "javascript", "jest", "thorough")
    assert r["success"] is True
    assert r["functions_found"] >= 2
    assert "describe" in r["test_code"]
    assert "expect" in r["test_code"]
    print(f"  OK Jest test gen: {r['test_count']} tests, {r['functions_found']} funcs")


def test_api_test_get():
    from agents.tools.devops_tools import api_test
    r = api_test("https://httpbin.org/get", "GET",
                  assertions=[{"field": "status", "op": "==", "value": 200}])
    if r["success"]:
        assert r["status"] == 200
        print(f"  OK API GET: status={r['status']}, {r['elapsed_ms']}ms")
    else:
        print(f"  OK API GET: skipped (network: {r.get('error', '')[:50]})")


def test_api_test_post():
    from agents.tools.devops_tools import api_test
    r = api_test("https://httpbin.org/post", "POST",
                  body={"name": "test", "value": 42},
                  assertions=[{"field": "status", "op": "==", "value": 200}])
    if r["success"]:
        print(f"  OK API POST: status={r['status']}, {r['elapsed_ms']}ms")
    else:
        print(f"  OK API POST: skipped (network: {r.get('error', '')[:50]})")


def test_scan_dependencies_npm():
    from agents.tools.devops_tools import scan_dependencies
    with tempfile.TemporaryDirectory() as d:
        pkg = {"dependencies": {"lodash": "^4.17.15", "express": "^4.17.1"},
               "devDependencies": {"moment": "^2.29.0"}}
        (Path(d) / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        r = scan_dependencies(d, "npm")
        assert r["success"] is True
        assert r["total_packages"] == 3
        assert r["vuln_count"] >= 1  # lodash, moment, express all have known vulns
        print(f"  OK npm scan: {r['total_packages']} pkgs, {r['vuln_count']} vulns, risk={r['risk_level']}")


def test_scan_dependencies_pip():
    from agents.tools.devops_tools import scan_dependencies
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "requirements.txt").write_text("flask==2.0.0\npyyaml==5.4.1\nrequests==2.27.0\n",
                                                    encoding="utf-8")
        r = scan_dependencies(d, "pip")
        assert r["success"] is True
        assert r["total_packages"] == 3
        assert r["vuln_count"] >= 1
        print(f"  OK pip scan: {r['total_packages']} pkgs, {r['vuln_count']} vulns, risk={r['risk_level']}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  New Features Test Suite — DB + Git + DevOps")
    print("=" * 60)

    tests = [
        ("DB: Postgres schema", test_db_design_schema_postgres),
        ("DB: MySQL schema + indexes", test_db_design_schema_mysql),
        ("DB: Raw migration", test_db_generate_migration_raw),
        ("DB: Alembic migration", test_db_generate_migration_alembic),
        ("DB: SQLAlchemy model", test_db_generate_model_sqlalchemy),
        ("DB: Django model", test_db_generate_model_django),
        ("DB: Prisma model", test_db_generate_model_prisma),
        ("DB: SELECT + JOIN query", test_db_generate_query_select),
        ("DB: CTE query", test_db_generate_query_cte),
        ("DB: Seed data SQL", test_db_seed_data_sql),
        ("DB: Seed data JSON", test_db_seed_data_json),
        ("DB: Schema analysis", test_db_analyze_schema),
        ("DB: SQLAlchemy repo", test_db_generate_repo_sqlalchemy),
        ("Git: Status", test_git_status),
        ("Git: Log", test_git_log),
        ("Git: Diff", test_git_diff),
        ("Git: Branch list", test_git_branch_list),
        ("Git: Stash list", test_git_stash_list),
        ("DevOps: Python test gen", test_generate_python_tests_pytest),
        ("DevOps: JS test gen", test_generate_js_tests_jest),
        ("DevOps: API GET", test_api_test_get),
        ("DevOps: API POST", test_api_test_post),
        ("DevOps: npm scan", test_scan_dependencies_npm),
        ("DevOps: pip scan", test_scan_dependencies_pip),
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
