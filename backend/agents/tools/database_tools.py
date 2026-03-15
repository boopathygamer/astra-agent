"""
Database Development Tools — Schema Design, Migrations, Queries & ORM Models.
==============================================================================
7 registered tools for professional database development:

  db_design_schema     — Generate SQL schema with constraints & indexes
  db_generate_migration— Create migration scripts (up/down) for schema changes
  db_generate_model    — Generate ORM model code (SQLAlchemy/Prisma/TypeORM/Django)
  db_generate_query    — Build complex SQL queries (joins, aggregations, CTEs)
  db_seed_data         — Generate realistic seed/fixture data
  db_analyze_schema    — Analyze schema for performance issues & best practices
  db_generate_repo     — Generate repository/DAO pattern code
"""

import json
import logging
import secrets
import textwrap
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from agents.tools.registry import registry, ToolRiskLevel

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# SQL Type Mappings
# ══════════════════════════════════════════════════════════════

_TYPE_MAP = {
    "string": {"postgres": "VARCHAR(255)", "mysql": "VARCHAR(255)", "sqlite": "TEXT"},
    "text": {"postgres": "TEXT", "mysql": "TEXT", "sqlite": "TEXT"},
    "integer": {"postgres": "INTEGER", "mysql": "INT", "sqlite": "INTEGER"},
    "bigint": {"postgres": "BIGINT", "mysql": "BIGINT", "sqlite": "INTEGER"},
    "float": {"postgres": "DOUBLE PRECISION", "mysql": "DOUBLE", "sqlite": "REAL"},
    "decimal": {"postgres": "DECIMAL(10,2)", "mysql": "DECIMAL(10,2)", "sqlite": "REAL"},
    "boolean": {"postgres": "BOOLEAN", "mysql": "TINYINT(1)", "sqlite": "INTEGER"},
    "date": {"postgres": "DATE", "mysql": "DATE", "sqlite": "TEXT"},
    "datetime": {"postgres": "TIMESTAMP", "mysql": "DATETIME", "sqlite": "TEXT"},
    "timestamp": {"postgres": "TIMESTAMP WITH TIME ZONE", "mysql": "TIMESTAMP", "sqlite": "TEXT"},
    "json": {"postgres": "JSONB", "mysql": "JSON", "sqlite": "TEXT"},
    "uuid": {"postgres": "UUID", "mysql": "CHAR(36)", "sqlite": "TEXT"},
    "blob": {"postgres": "BYTEA", "mysql": "BLOB", "sqlite": "BLOB"},
    "enum": {"postgres": "VARCHAR(50)", "mysql": "ENUM", "sqlite": "TEXT"},
}

_ORM_TYPE_MAP = {
    "string": {"sqlalchemy": "String(255)", "prisma": "String", "typeorm": "varchar", "django": "CharField(max_length=255)"},
    "text": {"sqlalchemy": "Text", "prisma": "String", "typeorm": "text", "django": "TextField()"},
    "integer": {"sqlalchemy": "Integer", "prisma": "Int", "typeorm": "int", "django": "IntegerField()"},
    "bigint": {"sqlalchemy": "BigInteger", "prisma": "BigInt", "typeorm": "bigint", "django": "BigIntegerField()"},
    "float": {"sqlalchemy": "Float", "prisma": "Float", "typeorm": "float", "django": "FloatField()"},
    "decimal": {"sqlalchemy": "Numeric(10,2)", "prisma": "Decimal", "typeorm": "decimal", "django": "DecimalField(max_digits=10, decimal_places=2)"},
    "boolean": {"sqlalchemy": "Boolean", "prisma": "Boolean", "typeorm": "boolean", "django": "BooleanField(default=False)"},
    "datetime": {"sqlalchemy": "DateTime", "prisma": "DateTime", "typeorm": "timestamp", "django": "DateTimeField()"},
    "json": {"sqlalchemy": "JSON", "prisma": "Json", "typeorm": "jsonb", "django": "JSONField(default=dict)"},
    "uuid": {"sqlalchemy": "UUID", "prisma": "String @default(uuid())", "typeorm": "uuid", "django": "UUIDField(default=uuid.uuid4)"},
}


# ══════════════════════════════════════════════════════════════
# Tool 1: db_design_schema
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="db_design_schema",
    description=(
        "Generate a complete SQL schema with tables, constraints, indexes, "
        "and foreign keys. Supports PostgreSQL, MySQL, and SQLite."
    ),
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "tables": "List of table definitions: [{name, columns: [{name, type, nullable, unique, default}], indexes}]",
        "dialect": "postgres | mysql | sqlite",
        "include_timestamps": "Add created_at/updated_at columns (default true)",
    },
)
def db_design_schema(
    tables: list = None,
    dialect: str = "postgres",
    include_timestamps: bool = True,
) -> Dict[str, Any]:
    """Generate SQL CREATE TABLE statements."""
    if not tables:
        tables = [
            {"name": "users", "columns": [
                {"name": "id", "type": "uuid", "primary": True},
                {"name": "email", "type": "string", "unique": True, "nullable": False},
                {"name": "name", "type": "string", "nullable": False},
                {"name": "password_hash", "type": "string", "nullable": False},
                {"name": "role", "type": "string", "default": "'user'"},
                {"name": "is_active", "type": "boolean", "default": "true"},
            ]},
        ]

    sql_parts = []
    for table in tables:
        tname = table["name"]
        cols = table.get("columns", [])
        indexes = table.get("indexes", [])

        col_defs = []
        constraints = []

        for col in cols:
            cname = col["name"]
            ctype = _TYPE_MAP.get(col.get("type", "string"), {}).get(dialect, "TEXT")
            parts = [f"    {cname} {ctype}"]

            if col.get("primary"):
                if dialect == "postgres" and col.get("type") == "uuid":
                    parts = [f"    {cname} UUID DEFAULT gen_random_uuid() PRIMARY KEY"]
                else:
                    parts.append("PRIMARY KEY")
            else:
                if not col.get("nullable", True):
                    parts.append("NOT NULL")
                if col.get("unique"):
                    parts.append("UNIQUE")
                if col.get("default") is not None:
                    parts.append(f"DEFAULT {col['default']}")

            col_defs.append(" ".join(parts))

            # Foreign key
            if col.get("references"):
                ref = col["references"]
                constraints.append(
                    f"    CONSTRAINT fk_{tname}_{cname} FOREIGN KEY ({cname}) "
                    f"REFERENCES {ref['table']}({ref.get('column', 'id')}) "
                    f"ON DELETE {ref.get('on_delete', 'CASCADE')}"
                )

        if include_timestamps:
            if dialect == "postgres":
                col_defs.append("    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()")
                col_defs.append("    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()")
            elif dialect == "mysql":
                col_defs.append("    created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
                col_defs.append("    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
            else:
                col_defs.append("    created_at TEXT DEFAULT (datetime('now'))")
                col_defs.append("    updated_at TEXT DEFAULT (datetime('now'))")

        all_defs = col_defs + constraints
        sql = f"CREATE TABLE IF NOT EXISTS {tname} (\n"
        sql += ",\n".join(all_defs)
        sql += "\n);\n"

        # Indexes
        for idx in indexes:
            idx_name = f"idx_{tname}_{'_'.join(idx['columns'])}"
            idx_type = "UNIQUE INDEX" if idx.get("unique") else "INDEX"
            sql += f"CREATE {idx_type} {idx_name} ON {tname} ({', '.join(idx['columns'])});\n"

        sql_parts.append(sql)

    full_sql = "\n".join(sql_parts)
    return {
        "success": True,
        "dialect": dialect,
        "tables_count": len(tables),
        "sql": full_sql,
    }


# ══════════════════════════════════════════════════════════════
# Tool 2: db_generate_migration
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="db_generate_migration",
    description="Generate database migration scripts with up/down methods.",
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "name": "Migration name (e.g. 'add_users_table')",
        "operations": "List of operations: [{type: create_table|add_column|drop_column|add_index, ...}]",
        "format": "raw_sql | alembic | prisma | knex",
    },
)
def db_generate_migration(
    name: str = "initial",
    operations: list = None,
    format: str = "raw_sql",
) -> Dict[str, Any]:
    """Generate migration scripts."""
    operations = operations or [
        {"type": "create_table", "table": "users", "columns": [
            {"name": "id", "type": "uuid", "primary": True},
            {"name": "email", "type": "string", "unique": True},
        ]}
    ]

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{name}"

    if format == "alembic":
        code = _gen_alembic_migration(name, operations, timestamp)
        filename += ".py"
    elif format == "knex":
        code = _gen_knex_migration(name, operations)
        filename += ".js"
    elif format == "prisma":
        code = _gen_prisma_migration(name, operations)
        filename += ".sql"
    else:
        code = _gen_raw_migration(name, operations)
        filename += ".sql"

    return {"success": True, "filename": filename, "format": format, "code": code,
            "operations_count": len(operations)}


def _gen_raw_migration(name, ops):
    up, down = [], []
    for op in ops:
        if op["type"] == "create_table":
            cols = ", ".join(f"{c['name']} TEXT" for c in op.get("columns", []))
            up.append(f"CREATE TABLE {op['table']} ({cols});")
            down.append(f"DROP TABLE IF EXISTS {op['table']};")
        elif op["type"] == "add_column":
            up.append(f"ALTER TABLE {op['table']} ADD COLUMN {op['column']} {op.get('col_type', 'TEXT')};")
            down.append(f"ALTER TABLE {op['table']} DROP COLUMN {op['column']};")
        elif op["type"] == "add_index":
            idx = f"idx_{op['table']}_{'_'.join(op['columns'])}"
            up.append(f"CREATE INDEX {idx} ON {op['table']} ({', '.join(op['columns'])});")
            down.append(f"DROP INDEX IF EXISTS {idx};")
    return f"-- UP\n{chr(10).join(up)}\n\n-- DOWN\n{chr(10).join(down)}"


def _gen_alembic_migration(name, ops, rev_id):
    up_ops, down_ops = [], []
    for op in ops:
        if op["type"] == "create_table":
            cols = ", ".join(f"sa.Column('{c['name']}', sa.Text)" for c in op.get("columns", []))
            up_ops.append(f"    op.create_table('{op['table']}', {cols})")
            down_ops.append(f"    op.drop_table('{op['table']}')")
        elif op["type"] == "add_column":
            up_ops.append(f"    op.add_column('{op['table']}', sa.Column('{op['column']}', sa.Text))")
            down_ops.append(f"    op.drop_column('{op['table']}', '{op['column']}')")
    return textwrap.dedent(f"""\
        \"\"\"Migration: {name}\"\"\"
        from alembic import op
        import sqlalchemy as sa

        revision = '{rev_id}'
        down_revision = None

        def upgrade():
        {chr(10).join(up_ops) or '    pass'}

        def downgrade():
        {chr(10).join(down_ops) or '    pass'}
    """)


def _gen_knex_migration(name, ops):
    up_ops, down_ops = [], []
    for op in ops:
        if op["type"] == "create_table":
            cols = "\n".join(f"      table.text('{c['name']}');" for c in op.get("columns", []))
            up_ops.append(f"    await knex.schema.createTable('{op['table']}', (table) => {{\n{cols}\n    }});")
            down_ops.append(f"    await knex.schema.dropTableIfExists('{op['table']}');")
    return textwrap.dedent(f"""\
        // Migration: {name}
        exports.up = async function(knex) {{
        {chr(10).join(up_ops)}
        }};

        exports.down = async function(knex) {{
        {chr(10).join(down_ops)}
        }};
    """)


def _gen_prisma_migration(name, ops):
    statements = []
    for op in ops:
        if op["type"] == "create_table":
            cols = "\n".join(f"    {c['name']} TEXT" for c in op.get("columns", []))
            statements.append(f"CREATE TABLE {op['table']} (\n{cols}\n);")
    return f"-- Migration: {name}\n\n" + "\n\n".join(statements)


# ══════════════════════════════════════════════════════════════
# Tool 3: db_generate_model
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="db_generate_model",
    description="Generate ORM model code for SQLAlchemy, Prisma, TypeORM, or Django.",
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "model_name": "Model/table name",
        "fields": "List of fields: [{name, type, nullable, unique, default, references}]",
        "orm": "sqlalchemy | prisma | typeorm | django",
    },
)
def db_generate_model(
    model_name: str = "User",
    fields: list = None,
    orm: str = "sqlalchemy",
) -> Dict[str, Any]:
    """Generate ORM model code."""
    fields = fields or [
        {"name": "id", "type": "uuid", "primary": True},
        {"name": "email", "type": "string", "unique": True},
        {"name": "name", "type": "string"},
    ]

    generators = {
        "sqlalchemy": _gen_sqlalchemy_model,
        "prisma": _gen_prisma_model,
        "typeorm": _gen_typeorm_model,
        "django": _gen_django_model,
    }

    gen = generators.get(orm)
    if not gen:
        return {"success": False, "error": f"Unsupported ORM: {orm}"}

    code = gen(model_name, fields)
    ext = {"sqlalchemy": "py", "prisma": "prisma", "typeorm": "ts", "django": "py"}
    return {"success": True, "model": model_name, "orm": orm,
            "filename": f"{model_name.lower()}.{ext[orm]}", "code": code}


def _gen_sqlalchemy_model(name, fields):
    table = name.lower() + "s"
    lines = [
        "from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text",
        "from sqlalchemy.dialects.postgresql import UUID, JSONB",
        "from sqlalchemy.orm import relationship",
        "from sqlalchemy.sql import func",
        "import uuid",
        "",
        "from .base import Base",
        "",
        f"class {name}(Base):",
        f"    __tablename__ = '{table}'",
        "",
    ]
    for f in fields:
        t = _ORM_TYPE_MAP.get(f.get("type", "string"), {}).get("sqlalchemy", "String(255)")
        parts = [f"    {f['name']} = Column({t}"]
        if f.get("primary"):
            parts.append(", primary_key=True, default=uuid.uuid4")
        if f.get("unique"):
            parts.append(", unique=True")
        if not f.get("nullable", True) and not f.get("primary"):
            parts.append(", nullable=False")
        if f.get("default") is not None:
            parts.append(f", default={f['default']}")
        parts.append(")")
        lines.append("".join(parts))

    lines.extend([
        "    created_at = Column(DateTime, server_default=func.now())",
        "    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())",
        "",
        "    def to_dict(self):",
        "        return {c.name: getattr(self, c.name) for c in self.__table__.columns}",
    ])
    return "\n".join(lines)


def _gen_prisma_model(name, fields):
    lines = [f"model {name} {{"]
    for f in fields:
        t = _ORM_TYPE_MAP.get(f.get("type", "string"), {}).get("prisma", "String")
        opt = "" if f.get("primary") or not f.get("nullable", True) else "?"
        decorators = []
        if f.get("primary"):
            decorators.append("@id @default(uuid())")
        if f.get("unique"):
            decorators.append("@unique")
        lines.append(f"  {f['name']}  {t}{opt}  {' '.join(decorators)}")
    lines.extend(["  createdAt  DateTime  @default(now())", "  updatedAt  DateTime  @updatedAt", "}"])
    return "\n".join(lines)


def _gen_typeorm_model(name, fields):
    lines = [
        'import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn, UpdateDateColumn } from "typeorm";',
        "",
        "@Entity()",
        f"export class {name} {{",
    ]
    for f in fields:
        t = _ORM_TYPE_MAP.get(f.get("type", "string"), {}).get("typeorm", "varchar")
        ts_type = {"string": "string", "integer": "number", "boolean": "boolean",
                    "datetime": "Date", "json": "object", "uuid": "string"}.get(f.get("type", "string"), "string")
        if f.get("primary"):
            lines.append(f'  @PrimaryGeneratedColumn("uuid")')
        else:
            opts = []
            if f.get("unique"):
                opts.append("unique: true")
            if f.get("nullable", True):
                opts.append("nullable: true")
            opt_str = ", ".join(opts)
            lines.append(f'  @Column({{ type: "{t}", {opt_str} }})')
        lines.append(f"  {f['name']}: {ts_type};")
        lines.append("")
    lines.extend([
        "  @CreateDateColumn()", "  createdAt: Date;", "",
        "  @UpdateDateColumn()", "  updatedAt: Date;", "}"
    ])
    return "\n".join(lines)


def _gen_django_model(name, fields):
    lines = [
        "import uuid",
        "from django.db import models",
        "",
        f"class {name}(models.Model):",
    ]
    for f in fields:
        t = _ORM_TYPE_MAP.get(f.get("type", "string"), {}).get("django", "CharField(max_length=255)")
        opts = []
        if f.get("primary"):
            t = "UUIDField(primary_key=True, default=uuid.uuid4, editable=False)"
        if f.get("unique") and not f.get("primary"):
            opts.append("unique=True")
        if f.get("nullable", True) and not f.get("primary"):
            opts.append("null=True, blank=True")
        if opts and not f.get("primary"):
            t = t.rstrip(")") + ", " + ", ".join(opts) + ")"
        lines.append(f"    {f['name']} = models.{t}")
    lines.extend([
        "    created_at = models.DateTimeField(auto_now_add=True)",
        "    updated_at = models.DateTimeField(auto_now=True)",
        "",
        "    class Meta:",
        f"        db_table = '{name.lower()}s'",
        f"        ordering = ['-created_at']",
        "",
        "    def __str__(self):",
        f"        return f'{name} {{self.pk}}'",
    ])
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# Tool 4: db_generate_query
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="db_generate_query",
    description="Build complex SQL queries with joins, aggregations, CTEs, and subqueries.",
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "query_type": "select | insert | update | delete | aggregate | cte",
        "table": "Main table name",
        "columns": "Columns to select",
        "joins": "List of joins: [{table, on, type}]",
        "where": "List of conditions: [{column, op, value}]",
        "group_by": "Group by columns",
        "order_by": "Order by columns",
        "limit": "Row limit",
    },
)
def db_generate_query(
    query_type: str = "select",
    table: str = "users",
    columns: list = None,
    joins: list = None,
    where: list = None,
    group_by: list = None,
    order_by: list = None,
    limit: int = None,
) -> Dict[str, Any]:
    """Build SQL queries."""
    columns = columns or ["*"]
    joins = joins or []
    where = where or []

    if query_type == "select":
        sql = f"SELECT {', '.join(columns)}\nFROM {table}"
        for j in joins:
            jtype = j.get("type", "INNER").upper()
            sql += f"\n{jtype} JOIN {j['table']} ON {j['on']}"
        if where:
            conditions = [f"{w['column']} {w.get('op', '=')} {w.get('value', '?')}" for w in where]
            sql += f"\nWHERE {' AND '.join(conditions)}"
        if group_by:
            sql += f"\nGROUP BY {', '.join(group_by)}"
        if order_by:
            sql += f"\nORDER BY {', '.join(order_by)}"
        if limit:
            sql += f"\nLIMIT {limit}"
        sql += ";"

    elif query_type == "aggregate":
        agg_cols = columns if columns != ["*"] else ["COUNT(*) AS total"]
        sql = f"SELECT {', '.join(agg_cols)}\nFROM {table}"
        if group_by:
            sql += f"\nGROUP BY {', '.join(group_by)}"
            sql += f"\nORDER BY total DESC"
        sql += ";"

    elif query_type == "cte":
        sql = f"WITH ranked AS (\n  SELECT *, ROW_NUMBER() OVER (ORDER BY created_at DESC) AS rn\n  FROM {table}"
        if where:
            conditions = [f"{w['column']} {w.get('op', '=')} {w.get('value', '?')}" for w in where]
            sql += f"\n  WHERE {' AND '.join(conditions)}"
        sql += f"\n)\nSELECT * FROM ranked WHERE rn <= {limit or 10};"

    else:
        sql = f"-- {query_type.upper()} query for {table}"

    return {"success": True, "query_type": query_type, "sql": sql}


# ══════════════════════════════════════════════════════════════
# Tool 5: db_seed_data
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="db_seed_data",
    description="Generate realistic seed/fixture data for database tables.",
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "table": "Table name",
        "columns": "List of column configs: [{name, type, values}]",
        "count": "Number of rows to generate",
        "format": "sql | json | csv",
    },
)
def db_seed_data(
    table: str = "users",
    columns: list = None,
    count: int = 10,
    format: str = "sql",
) -> Dict[str, Any]:
    """Generate seed data."""
    columns = columns or [
        {"name": "id", "type": "uuid"},
        {"name": "email", "type": "email"},
        {"name": "name", "type": "name"},
        {"name": "is_active", "type": "boolean"},
    ]

    _NAMES = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry", "Iris", "Jack",
              "Karen", "Leo", "Maya", "Noah", "Olivia", "Peter", "Quinn", "Rose", "Sam", "Tina"]
    _DOMAINS = ["gmail.com", "outlook.com", "yahoo.com", "proton.me", "company.io"]

    rows = []
    for i in range(count):
        row = {}
        for col in columns:
            ct = col.get("type", "string")
            if col.get("values"):
                row[col["name"]] = col["values"][i % len(col["values"])]
            elif ct == "uuid":
                row[col["name"]] = secrets.token_hex(16)
            elif ct == "email":
                name = _NAMES[i % len(_NAMES)].lower()
                row[col["name"]] = f"{name}{i}@{_DOMAINS[i % len(_DOMAINS)]}"
            elif ct == "name":
                row[col["name"]] = _NAMES[i % len(_NAMES)]
            elif ct == "boolean":
                row[col["name"]] = i % 3 != 0
            elif ct == "integer":
                row[col["name"]] = (i + 1) * 10
            elif ct == "float":
                row[col["name"]] = round((i + 1) * 9.99, 2)
            elif ct == "date":
                row[col["name"]] = (datetime.now() - timedelta(days=i * 7)).strftime("%Y-%m-%d")
            else:
                row[col["name"]] = f"{col['name']}_{i+1}"
        rows.append(row)

    if format == "sql":
        col_names = ", ".join(c["name"] for c in columns)
        values = []
        for r in rows:
            vals = []
            for c in columns:
                v = r[c["name"]]
                if isinstance(v, bool):
                    vals.append("true" if v else "false")
                elif isinstance(v, (int, float)):
                    vals.append(str(v))
                else:
                    vals.append(f"'{v}'")
            values.append(f"({', '.join(vals)})")
        data = f"INSERT INTO {table} ({col_names}) VALUES\n" + ",\n".join(values) + ";"
    elif format == "json":
        data = json.dumps(rows, indent=2, default=str)
    else:
        header = ",".join(c["name"] for c in columns)
        csv_rows = [",".join(str(r[c["name"]]) for c in columns) for r in rows]
        data = header + "\n" + "\n".join(csv_rows)

    return {"success": True, "table": table, "rows": count, "format": format, "data": data}


# ══════════════════════════════════════════════════════════════
# Tool 6: db_analyze_schema
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="db_analyze_schema",
    description="Analyze a database schema for performance issues, missing indexes, and best practices.",
    risk_level=ToolRiskLevel.LOW,
    parameters={"schema_sql": "SQL CREATE TABLE statements to analyze"},
)
def db_analyze_schema(schema_sql: str = "") -> Dict[str, Any]:
    """Analyze schema for issues."""
    issues = []
    suggestions = []

    sql_upper = schema_sql.upper()
    sql_lower = schema_sql.lower()

    # Check for primary keys
    if "CREATE TABLE" in sql_upper and "PRIMARY KEY" not in sql_upper:
        issues.append({"severity": "critical", "message": "Table missing PRIMARY KEY"})

    # Check for timestamps
    if "created_at" not in sql_lower:
        suggestions.append("Add created_at timestamp for audit trails")
    if "updated_at" not in sql_lower:
        suggestions.append("Add updated_at timestamp for change tracking")

    # Check for indexes on foreign keys
    if "FOREIGN KEY" in sql_upper and "INDEX" not in sql_upper:
        issues.append({"severity": "warning", "message": "Foreign keys without indexes — slow JOIN performance"})
        suggestions.append("Add indexes on all foreign key columns")

    # Check for VARCHAR without length
    if "VARCHAR" in sql_upper and "VARCHAR()" in sql_upper:
        issues.append({"severity": "warning", "message": "VARCHAR without length specification"})

    # Check for proper naming
    if any(c in schema_sql for c in ["camelCase", "CamelCase"]):
        suggestions.append("Use snake_case for table and column names")

    # Data type suggestions
    if "CHAR(36)" in sql_upper:
        suggestions.append("Consider native UUID type instead of CHAR(36)")
    if "TEXT" in sql_upper and "VARCHAR" not in sql_upper:
        suggestions.append("Use VARCHAR(n) for fields with known max length for better performance")

    # General best practices
    suggestions.extend([
        "Add NOT NULL constraints where data is always required",
        "Use ENUM or CHECK constraints for status fields",
        "Consider partitioning for tables > 10M rows",
    ])

    score = 100 - len(issues) * 15 - max(0, len(suggestions) - 3) * 5
    return {
        "success": True,
        "issues": issues,
        "suggestions": suggestions[:10],
        "score": max(0, min(100, score)),
        "grade": "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D",
    }


# ══════════════════════════════════════════════════════════════
# Tool 7: db_generate_repo
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="db_generate_repo",
    description="Generate repository/DAO pattern code with CRUD operations.",
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "model_name": "Model name",
        "orm": "sqlalchemy | prisma | typeorm | raw_sql",
        "operations": "CRUD operations to include",
    },
)
def db_generate_repo(
    model_name: str = "User",
    orm: str = "sqlalchemy",
    operations: list = None,
) -> Dict[str, Any]:
    """Generate repository pattern code."""
    operations = operations or ["create", "get_by_id", "get_all", "update", "delete", "search"]

    if orm == "sqlalchemy":
        code = _gen_sqlalchemy_repo(model_name, operations)
    elif orm == "typeorm":
        code = _gen_typeorm_repo(model_name, operations)
    else:
        code = _gen_raw_repo(model_name, operations)

    ext = {"sqlalchemy": "py", "typeorm": "ts", "raw_sql": "py"}.get(orm, "py")
    return {"success": True, "model": model_name, "orm": orm,
            "filename": f"{model_name.lower()}_repository.{ext}", "code": code,
            "operations": operations}


def _gen_sqlalchemy_repo(name, ops):
    lower = name.lower()
    lines = [
        f"from typing import List, Optional",
        f"from sqlalchemy.orm import Session",
        f"from .{lower} import {name}",
        "",
        f"class {name}Repository:",
        f"    def __init__(self, db: Session):",
        f"        self.db = db",
        "",
    ]
    if "create" in ops:
        lines.extend([
            f"    def create(self, **kwargs) -> {name}:",
            f"        obj = {name}(**kwargs)",
            f"        self.db.add(obj)",
            f"        self.db.commit()",
            f"        self.db.refresh(obj)",
            f"        return obj",
            "",
        ])
    if "get_by_id" in ops:
        lines.extend([
            f"    def get_by_id(self, id) -> Optional[{name}]:",
            f"        return self.db.query({name}).filter({name}.id == id).first()",
            "",
        ])
    if "get_all" in ops:
        lines.extend([
            f"    def get_all(self, skip=0, limit=100) -> List[{name}]:",
            f"        return self.db.query({name}).offset(skip).limit(limit).all()",
            "",
        ])
    if "update" in ops:
        lines.extend([
            f"    def update(self, id, **kwargs) -> Optional[{name}]:",
            f"        obj = self.get_by_id(id)",
            f"        if not obj: return None",
            f"        for k, v in kwargs.items(): setattr(obj, k, v)",
            f"        self.db.commit()",
            f"        self.db.refresh(obj)",
            f"        return obj",
            "",
        ])
    if "delete" in ops:
        lines.extend([
            f"    def delete(self, id) -> bool:",
            f"        obj = self.get_by_id(id)",
            f"        if not obj: return False",
            f"        self.db.delete(obj)",
            f"        self.db.commit()",
            f"        return True",
            "",
        ])
    if "search" in ops:
        lines.extend([
            f"    def search(self, **filters) -> List[{name}]:",
            f"        query = self.db.query({name})",
            f"        for k, v in filters.items():",
            f"            if hasattr({name}, k):",
            f"                query = query.filter(getattr({name}, k).ilike(f'%{{v}}%'))",
            f"        return query.all()",
        ])
    return "\n".join(lines)


def _gen_typeorm_repo(name, ops):
    lower = name.lower()
    lines = [
        f'import {{ Repository }} from "typeorm";',
        f'import {{ {name} }} from "./{lower}";',
        "",
        f"export class {name}Repository extends Repository<{name}> {{",
    ]
    if "get_all" in ops:
        lines.extend([
            f"  async findAll(skip = 0, take = 100): Promise<{name}[]> {{",
            f"    return this.find({{ skip, take, order: {{ createdAt: 'DESC' }} }});",
            f"  }}",
        ])
    if "search" in ops:
        lines.extend([
            f"  async search(query: string): Promise<{name}[]> {{",
            f'    return this.createQueryBuilder("{lower}")',
            f'      .where("{lower}.name ILIKE :q", {{ q: `%${{query}}%` }})',
            f"      .getMany();",
            f"  }}",
        ])
    lines.append("}")
    return "\n".join(lines)


def _gen_raw_repo(name, ops):
    lower = name.lower()
    table = lower + "s"
    lines = [
        f"import sqlite3",
        f"from typing import List, Optional, Dict",
        "",
        f"class {name}Repository:",
        f"    def __init__(self, db_path: str):",
        f"        self.db_path = db_path",
        "",
        f"    def _conn(self):",
        f"        conn = sqlite3.connect(self.db_path)",
        f"        conn.row_factory = sqlite3.Row",
        f"        return conn",
        "",
    ]
    if "create" in ops:
        lines.extend([
            f"    def create(self, data: Dict) -> Dict:",
            f"        conn = self._conn()",
            f"        cols = ', '.join(data.keys())",
            f"        vals = ', '.join('?' for _ in data)",
            f"        conn.execute(f'INSERT INTO {table} ({{cols}}) VALUES ({{vals}})', list(data.values()))",
            f"        conn.commit()",
            f"        conn.close()",
            f"        return data",
            "",
        ])
    if "get_by_id" in ops:
        lines.extend([
            f"    def get_by_id(self, id) -> Optional[Dict]:",
            f"        conn = self._conn()",
            f"        row = conn.execute('SELECT * FROM {table} WHERE id = ?', (id,)).fetchone()",
            f"        conn.close()",
            f"        return dict(row) if row else None",
            "",
        ])
    return "\n".join(lines)
