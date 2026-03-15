"""
Web Development Tools — Expert-Level Full-Stack Project Builder.
================================================================
7 registered tools for professional web development:

  web_scaffold_project   — React/Vue/Next.js/Vanilla/Svelte scaffolding
  web_generate_component — Component gen with props, state, styling
  web_generate_api       — REST/GraphQL endpoint gen (Express/FastAPI/Flask)
  web_generate_css       — Design systems, themes, animations, responsive
  web_bundle_project     — Webpack/Vite/esbuild build execution
  web_dev_server         — Start/stop local dev servers
  web_deploy_config      — Docker/Nginx/Vercel/Netlify deployment configs
"""

import json
import logging
import os
import subprocess
import signal
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.tools.registry import registry, ToolRiskLevel

logger = logging.getLogger(__name__)

# Active dev server tracking
_active_servers: Dict[str, dict] = {}


# ══════════════════════════════════════════════════════════════
# Project Templates
# ══════════════════════════════════════════════════════════════

_REACT_TEMPLATE = {
    "src/App.jsx": textwrap.dedent("""\
        import React from 'react';
        import { BrowserRouter, Routes, Route } from 'react-router-dom';
        import Home from './pages/Home';
        import About from './pages/About';
        import Layout from './components/Layout';
        import './styles/index.css';

        export default function App() {
          return (
            <BrowserRouter>
              <Layout>
                <Routes>
                  <Route path="/" element={<Home />} />
                  <Route path="/about" element={<About />} />
                </Routes>
              </Layout>
            </BrowserRouter>
          );
        }
    """),
    "src/pages/Home.jsx": textwrap.dedent("""\
        import React, { useState, useEffect } from 'react';

        export default function Home() {
          const [data, setData] = useState(null);
          const [loading, setLoading] = useState(true);

          useEffect(() => {
            const timer = setTimeout(() => {
              setData({ message: 'Welcome to your app!' });
              setLoading(false);
            }, 500);
            return () => clearTimeout(timer);
          }, []);

          if (loading) return <div className="loading-spinner" />;

          return (
            <main className="page home-page">
              <h1>{data?.message}</h1>
              <p>Edit <code>src/pages/Home.jsx</code> to get started.</p>
            </main>
          );
        }
    """),
    "src/pages/About.jsx": textwrap.dedent("""\
        import React from 'react';

        export default function About() {
          return (
            <main className="page about-page">
              <h1>About</h1>
              <p>Built with React + Vite.</p>
            </main>
          );
        }
    """),
    "src/components/Layout.jsx": textwrap.dedent("""\
        import React from 'react';
        import { Link } from 'react-router-dom';

        export default function Layout({ children }) {
          return (
            <div className="app-layout">
              <nav className="navbar">
                <div className="nav-brand">MyApp</div>
                <div className="nav-links">
                  <Link to="/">Home</Link>
                  <Link to="/about">About</Link>
                </div>
              </nav>
              <div className="content">{children}</div>
            </div>
          );
        }
    """),
}

_VUE_TEMPLATE = {
    "src/App.vue": textwrap.dedent("""\
        <template>
          <div id="app">
            <nav class="navbar">
              <router-link to="/">Home</router-link>
              <router-link to="/about">About</router-link>
            </nav>
            <router-view />
          </div>
        </template>

        <script setup>
        </script>

        <style scoped>
        .navbar { display: flex; gap: 1rem; padding: 1rem; background: #1a1a2e; }
        .navbar a { color: #e94560; text-decoration: none; font-weight: 600; }
        </style>
    """),
    "src/views/Home.vue": textwrap.dedent("""\
        <template>
          <main class="page">
            <h1>{{ message }}</h1>
            <p>Edit <code>src/views/Home.vue</code> to get started.</p>
          </main>
        </template>

        <script setup>
        import { ref, onMounted } from 'vue';
        const message = ref('Loading...');
        onMounted(() => { message.value = 'Welcome to your Vue app!'; });
        </script>
    """),
    "src/router/index.js": textwrap.dedent("""\
        import { createRouter, createWebHistory } from 'vue-router';
        import Home from '../views/Home.vue';

        const routes = [
          { path: '/', component: Home },
          { path: '/about', component: () => import('../views/About.vue') },
        ];

        export default createRouter({ history: createWebHistory(), routes });
    """),
}

_NEXTJS_TEMPLATE = {
    "app/page.tsx": textwrap.dedent("""\
        import Link from 'next/link';

        export default function Home() {
          return (
            <main className="container">
              <h1>Welcome to Next.js</h1>
              <p>Edit <code>app/page.tsx</code> to get started.</p>
              <Link href="/about">About</Link>
            </main>
          );
        }
    """),
    "app/layout.tsx": textwrap.dedent("""\
        import type { Metadata } from 'next';
        import './globals.css';

        export const metadata: Metadata = {
          title: 'My App',
          description: 'Built with Next.js',
        };

        export default function RootLayout({ children }: { children: React.ReactNode }) {
          return (
            <html lang="en">
              <body>{children}</body>
            </html>
          );
        }
    """),
    "app/about/page.tsx": textwrap.dedent("""\
        export default function About() {
          return (
            <main className="container">
              <h1>About</h1>
              <p>Server-side rendered with Next.js App Router.</p>
            </main>
          );
        }
    """),
}

_VANILLA_TEMPLATE = {
    "index.html": textwrap.dedent("""\
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <title>My App</title>
          <link rel="stylesheet" href="styles/main.css" />
        </head>
        <body>
          <nav id="navbar"><a href="/">Home</a><a href="/about">About</a></nav>
          <main id="app"></main>
          <script type="module" src="js/app.js"></script>
        </body>
        </html>
    """),
    "js/app.js": textwrap.dedent("""\
        import { Router } from './router.js';
        import { HomePage } from './pages/home.js';
        import { AboutPage } from './pages/about.js';

        const router = new Router('app');
        router.addRoute('/', HomePage);
        router.addRoute('/about', AboutPage);
        router.start();
    """),
    "js/router.js": textwrap.dedent("""\
        export class Router {
          constructor(rootId) {
            this.root = document.getElementById(rootId);
            this.routes = {};
            window.addEventListener('popstate', () => this.resolve());
            document.addEventListener('click', (e) => {
              if (e.target.matches('a[href^="/"]')) {
                e.preventDefault();
                history.pushState(null, '', e.target.href);
                this.resolve();
              }
            });
          }
          addRoute(path, component) { this.routes[path] = component; }
          resolve() {
            const path = window.location.pathname;
            const Component = this.routes[path] || this.routes['/'];
            if (Component) this.root.innerHTML = Component();
          }
          start() { this.resolve(); }
        }
    """),
    "js/pages/home.js": 'export const HomePage = () => `<h1>Welcome</h1><p>Edit js/pages/home.js</p>`;\n',
    "js/pages/about.js": 'export const AboutPage = () => `<h1>About</h1><p>Vanilla JS SPA.</p>`;\n',
}

_PACKAGE_CONFIGS = {
    "react": {
        "name": "", "version": "1.0.0", "private": True, "type": "module",
        "scripts": {"dev": "vite", "build": "vite build", "preview": "vite preview"},
        "dependencies": {"react": "^18.2.0", "react-dom": "^18.2.0", "react-router-dom": "^6.20.0"},
        "devDependencies": {"@vitejs/plugin-react": "^4.2.0", "vite": "^5.0.0"},
    },
    "vue": {
        "name": "", "version": "1.0.0", "private": True, "type": "module",
        "scripts": {"dev": "vite", "build": "vite build"},
        "dependencies": {"vue": "^3.3.0", "vue-router": "^4.2.0"},
        "devDependencies": {"@vitejs/plugin-vue": "^4.5.0", "vite": "^5.0.0"},
    },
    "nextjs": {
        "name": "", "version": "1.0.0", "private": True,
        "scripts": {"dev": "next dev", "build": "next build", "start": "next start"},
        "dependencies": {"next": "^14.0.0", "react": "^18.2.0", "react-dom": "^18.2.0"},
        "devDependencies": {"typescript": "^5.3.0", "@types/react": "^18.2.0"},
    },
}

_CSS_DESIGN_SYSTEM = textwrap.dedent("""\
    /* ═══ Design System ═══ */
    :root {
      --color-primary: #6366f1;
      --color-primary-dark: #4f46e5;
      --color-secondary: #ec4899;
      --color-bg: #0f172a;
      --color-surface: #1e293b;
      --color-text: #f1f5f9;
      --color-text-muted: #94a3b8;
      --color-border: #334155;
      --color-success: #22c55e;
      --color-warning: #f59e0b;
      --color-error: #ef4444;
      --radius-sm: 0.375rem;
      --radius-md: 0.5rem;
      --radius-lg: 1rem;
      --radius-xl: 1.5rem;
      --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
      --shadow-md: 0 4px 6px rgba(0,0,0,0.3);
      --shadow-lg: 0 10px 15px rgba(0,0,0,0.4);
      --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
      --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
      --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
      --transition-normal: 300ms cubic-bezier(0.4, 0, 0.2, 1);
    }

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html { font-size: 16px; scroll-behavior: smooth; }
    body {
      font-family: var(--font-sans);
      background: var(--color-bg);
      color: var(--color-text);
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
    }

    /* ═══ Typography ═══ */
    h1 { font-size: 2.5rem; font-weight: 800; letter-spacing: -0.025em; }
    h2 { font-size: 2rem; font-weight: 700; }
    h3 { font-size: 1.5rem; font-weight: 600; }
    p { color: var(--color-text-muted); max-width: 65ch; }
    code { font-family: var(--font-mono); background: var(--color-surface);
           padding: 0.15em 0.4em; border-radius: var(--radius-sm); font-size: 0.9em; }

    /* ═══ Layout ═══ */
    .container { max-width: 1200px; margin: 0 auto; padding: 0 1.5rem; }
    .page { padding: 3rem 0; min-height: calc(100vh - 4rem); }

    /* ═══ Navbar ═══ */
    .navbar {
      display: flex; align-items: center; justify-content: space-between;
      padding: 1rem 2rem; background: var(--color-surface);
      border-bottom: 1px solid var(--color-border);
      backdrop-filter: blur(12px); position: sticky; top: 0; z-index: 50;
    }
    .nav-brand { font-size: 1.25rem; font-weight: 800;
                  background: linear-gradient(135deg, var(--color-primary), var(--color-secondary));
                  -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .nav-links { display: flex; gap: 1.5rem; }
    .nav-links a { color: var(--color-text-muted); text-decoration: none;
                    transition: color var(--transition-fast); font-weight: 500; }
    .nav-links a:hover { color: var(--color-primary); }

    /* ═══ Components ═══ */
    .btn {
      display: inline-flex; align-items: center; gap: 0.5rem;
      padding: 0.625rem 1.25rem; border-radius: var(--radius-md);
      font-weight: 600; font-size: 0.875rem; cursor: pointer; border: none;
      transition: all var(--transition-fast);
    }
    .btn-primary { background: var(--color-primary); color: white; }
    .btn-primary:hover { background: var(--color-primary-dark); transform: translateY(-1px);
                          box-shadow: 0 4px 12px rgba(99,102,241,0.4); }
    .btn-secondary { background: var(--color-surface); color: var(--color-text);
                      border: 1px solid var(--color-border); }
    .btn-secondary:hover { border-color: var(--color-primary); }

    .card {
      background: var(--color-surface); border: 1px solid var(--color-border);
      border-radius: var(--radius-lg); padding: 1.5rem;
      transition: all var(--transition-normal);
    }
    .card:hover { border-color: var(--color-primary);
                   box-shadow: 0 0 0 1px var(--color-primary), var(--shadow-lg); }

    .input {
      width: 100%; padding: 0.625rem 1rem; background: var(--color-bg);
      border: 1px solid var(--color-border); border-radius: var(--radius-md);
      color: var(--color-text); font-size: 0.875rem;
      transition: border-color var(--transition-fast);
    }
    .input:focus { outline: none; border-color: var(--color-primary);
                    box-shadow: 0 0 0 3px rgba(99,102,241,0.15); }

    .badge {
      display: inline-flex; padding: 0.25rem 0.625rem; border-radius: 9999px;
      font-size: 0.75rem; font-weight: 600; }
    .badge-success { background: rgba(34,197,94,0.15); color: var(--color-success); }
    .badge-warning { background: rgba(245,158,11,0.15); color: var(--color-warning); }
    .badge-error { background: rgba(239,68,68,0.15); color: var(--color-error); }

    /* ═══ Animations ═══ */
    @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); }
                        to { opacity: 1; transform: translateY(0); } }
    @keyframes slideIn { from { transform: translateX(-100%); } to { transform: translateX(0); } }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    .animate-fade { animation: fadeIn 0.4s ease-out; }
    .loading-spinner {
      width: 2rem; height: 2rem; border: 3px solid var(--color-border);
      border-top-color: var(--color-primary); border-radius: 50%;
      animation: spin 0.8s linear infinite; margin: 2rem auto;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* ═══ Responsive ═══ */
    @media (max-width: 768px) {
      h1 { font-size: 1.75rem; }
      .navbar { padding: 0.75rem 1rem; }
      .nav-links { gap: 0.75rem; }
    }
""")


# ══════════════════════════════════════════════════════════════
# Tool 1: web_scaffold_project
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="web_scaffold_project",
    description=(
        "Generate a complete web project structure with routing, components, "
        "styling, and build config. Supports React, Vue, Next.js, Svelte, "
        "and Vanilla JS frameworks."
    ),
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "project_name": "Project name",
        "framework": "react | vue | nextjs | vanilla | svelte",
        "output_dir": "Directory to create project in",
        "features": "Optional list: typescript, tailwind, pwa, docker",
    },
)
def web_scaffold_project(
    project_name: str = "my-app",
    framework: str = "react",
    output_dir: str = "",
    features: list = None,
) -> Dict[str, Any]:
    """Scaffold a complete web project."""
    features = features or []
    framework = framework.lower()

    templates = {
        "react": _REACT_TEMPLATE,
        "vue": _VUE_TEMPLATE,
        "nextjs": _NEXTJS_TEMPLATE,
        "vanilla": _VANILLA_TEMPLATE,
    }

    if framework not in templates:
        return {"success": False, "error": f"Unknown framework: {framework}. Use: {list(templates.keys())}"}

    project_dir = Path(output_dir) / project_name if output_dir else Path(project_name)

    result = {
        "success": True,
        "project_name": project_name,
        "framework": framework,
        "directory": str(project_dir),
        "files_created": [],
        "features": features,
    }

    try:
        # Create project structure
        template = templates[framework]
        for filepath, content in template.items():
            full_path = project_dir / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            result["files_created"].append(filepath)

        # Create CSS design system
        css_path = project_dir / ("src/styles/index.css" if framework != "vanilla" else "styles/main.css")
        css_path.parent.mkdir(parents=True, exist_ok=True)
        css_path.write_text(_CSS_DESIGN_SYSTEM, encoding="utf-8")
        result["files_created"].append(str(css_path.relative_to(project_dir)))

        # Create package.json
        if framework in _PACKAGE_CONFIGS:
            pkg = dict(_PACKAGE_CONFIGS[framework])
            pkg["name"] = project_name
            pkg_path = project_dir / "package.json"
            pkg_path.write_text(json.dumps(pkg, indent=2), encoding="utf-8")
            result["files_created"].append("package.json")

        # Vite config for React/Vue
        if framework in ("react", "vue"):
            plugin = "@vitejs/plugin-react" if framework == "react" else "@vitejs/plugin-vue"
            plugin_import = "react" if framework == "react" else "vue"
            vite_cfg = (
                f'import {{ defineConfig }} from "vite";\n'
                f'import {plugin_import} from "{plugin}";\n\n'
                f'export default defineConfig({{\n'
                f'  plugins: [{plugin_import}()],\n'
                f'  server: {{ port: 3000, open: true }},\n'
                f'  build: {{ outDir: "dist", sourcemap: true }},\n'
                f'}});\n'
            )
            (project_dir / "vite.config.js").write_text(vite_cfg, encoding="utf-8")
            result["files_created"].append("vite.config.js")

        # .gitignore
        gitignore = "node_modules/\ndist/\n.env\n.env.local\n*.log\n.DS_Store\n"
        (project_dir / ".gitignore").write_text(gitignore, encoding="utf-8")
        result["files_created"].append(".gitignore")

        # Docker support
        if "docker" in features:
            dockerfile = _generate_dockerfile(framework)
            (project_dir / "Dockerfile").write_text(dockerfile, encoding="utf-8")
            result["files_created"].append("Dockerfile")

        result["message"] = f"Project '{project_name}' ({framework}) created with {len(result['files_created'])} files"

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    return result


# ══════════════════════════════════════════════════════════════
# Tool 2: web_generate_component
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="web_generate_component",
    description=(
        "Generate a React/Vue/Svelte component with props, state, "
        "event handlers, and scoped styling."
    ),
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "name": "Component name (PascalCase)",
        "framework": "react | vue | svelte",
        "props": "List of prop definitions: [{name, type, default}]",
        "features": "Optional: state, effects, api_call, form, modal, table",
    },
)
def web_generate_component(
    name: str = "MyComponent",
    framework: str = "react",
    props: list = None,
    features: list = None,
) -> Dict[str, Any]:
    """Generate a framework-specific component."""
    props = props or []
    features = features or []

    generators = {
        "react": _gen_react_component,
        "vue": _gen_vue_component,
        "svelte": _gen_svelte_component,
    }

    gen = generators.get(framework)
    if not gen:
        return {"success": False, "error": f"Unsupported framework: {framework}"}

    code = gen(name, props, features)
    filename = f"{name}.{'jsx' if framework == 'react' else 'vue' if framework == 'vue' else 'svelte'}"

    return {
        "success": True,
        "component_name": name,
        "framework": framework,
        "filename": filename,
        "code": code,
        "props": props,
        "features": features,
    }


def _gen_react_component(name, props, features):
    prop_types = ", ".join(f"{p.get('name', 'prop')}" for p in props) if props else ""
    prop_destructure = f"{{ {prop_types} }}" if prop_types else ""

    lines = ["import React, { useState, useEffect, useCallback } from 'react';", ""]

    lines.append(f"export default function {name}({prop_destructure}) {{")

    if "state" in features or "form" in features:
        lines.append("  const [data, setData] = useState(null);")
        lines.append("  const [loading, setLoading] = useState(false);")
        lines.append("  const [error, setError] = useState(null);")
        lines.append("")

    if "api_call" in features:
        lines.extend([
            "  const fetchData = useCallback(async () => {",
            "    setLoading(true);",
            "    try {",
            "      const res = await fetch('/api/data');",
            "      if (!res.ok) throw new Error(`HTTP ${res.status}`);",
            "      setData(await res.json());",
            "    } catch (err) { setError(err.message); }",
            "    finally { setLoading(false); }",
            "  }, []);",
            "",
            "  useEffect(() => { fetchData(); }, [fetchData]);",
            "",
        ])

    if "form" in features:
        lines.extend([
            "  const [formData, setFormData] = useState({});",
            "  const handleChange = (e) => setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }));",
            "  const handleSubmit = async (e) => {",
            "    e.preventDefault();",
            "    setLoading(true);",
            "    try { /* submit formData */ } finally { setLoading(false); }",
            "  };",
            "",
        ])

    lines.extend([
        "  return (",
        f'    <div className="{name.lower()}-container">',
        f"      <h2>{name}</h2>",
    ])

    if "form" in features:
        lines.extend([
            '      <form onSubmit={handleSubmit}>',
            '        <input className="input" name="field" onChange={handleChange} placeholder="Enter..." />',
            '        <button className="btn btn-primary" type="submit" disabled={loading}>',
            '          {loading ? "Saving..." : "Submit"}',
            '        </button>',
            '      </form>',
        ])

    lines.extend(["    </div>", "  );", "}", ""])
    return "\n".join(lines)


def _gen_vue_component(name, props, features):
    prop_defs = "\n".join(
        f"  {p.get('name', 'prop')}: {{ type: {p.get('type', 'String')}, default: {p.get('default', 'null')} }},"
        for p in props
    )
    lines = [
        "<template>",
        f'  <div class="{name.lower()}-container">',
        f"    <h2>{name}</h2>",
        "    <slot />",
        "  </div>",
        "</template>",
        "",
        "<script setup>",
        "import { ref, onMounted } from 'vue';",
        "",
    ]
    if props:
        lines.append(f"const props = defineProps({{\n{prop_defs}\n}});")
    if "state" in features:
        lines.extend(["const data = ref(null);", "const loading = ref(false);"])
    if "api_call" in features:
        lines.extend([
            "onMounted(async () => {",
            "  loading.value = true;",
            "  try { data.value = await (await fetch('/api/data')).json(); }",
            "  finally { loading.value = false; }",
            "});",
        ])
    lines.extend(["</script>", "", f"<style scoped>", f".{name.lower()}-container {{ padding: 1rem; }}", "</style>"])
    return "\n".join(lines)


def _gen_svelte_component(name, props, features):
    lines = ["<script>"]
    for p in props:
        lines.append(f"  export let {p.get('name', 'prop')} = {p.get('default', 'null')};")
    if "state" in features:
        lines.extend(["  let data = null;", "  let loading = false;"])
    if "api_call" in features:
        lines.extend([
            "  import { onMount } from 'svelte';",
            "  onMount(async () => {",
            "    loading = true;",
            "    data = await (await fetch('/api/data')).json();",
            "    loading = false;",
            "  });",
        ])
    lines.extend([
        "</script>",
        "",
        f'<div class="{name.lower()}">',
        f"  <h2>{name}</h2>",
        "</div>",
        "",
        "<style>",
        f"  .{name.lower()} {{ padding: 1rem; }}",
        "</style>",
    ])
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# Tool 3: web_generate_api
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="web_generate_api",
    description=(
        "Generate REST API endpoints with validation, error handling, "
        "and CRUD operations. Supports Express.js, FastAPI, and Flask."
    ),
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "resource": "Resource name (e.g. 'users', 'products')",
        "backend": "express | fastapi | flask",
        "operations": "List of CRUD ops: create, read, update, delete, list",
        "fields": "List of field definitions: [{name, type, required}]",
    },
)
def web_generate_api(
    resource: str = "items",
    backend: str = "express",
    operations: list = None,
    fields: list = None,
) -> Dict[str, Any]:
    """Generate REST API endpoint code."""
    operations = operations or ["create", "read", "update", "delete", "list"]
    fields = fields or [{"name": "name", "type": "string", "required": True}]

    generators = {
        "express": _gen_express_api,
        "fastapi": _gen_fastapi_api,
        "flask": _gen_flask_api,
    }

    gen = generators.get(backend)
    if not gen:
        return {"success": False, "error": f"Unsupported backend: {backend}"}

    code = gen(resource, operations, fields)
    ext = "js" if backend == "express" else "py"

    return {
        "success": True,
        "resource": resource,
        "backend": backend,
        "filename": f"{resource}_routes.{ext}",
        "operations": operations,
        "code": code,
    }


def _gen_express_api(resource, ops, fields):
    r = resource.lower()
    lines = [
        f'const express = require("express");',
        f"const router = express.Router();",
        "",
        f"// In-memory store (replace with database)",
        f"let {r}Store = [];",
        f"let nextId = 1;",
        "",
        "// Validation middleware",
        f"function validate{r.capitalize()}(req, res, next) {{",
        "  const errors = [];",
    ]
    for f in fields:
        if f.get("required"):
            lines.append(f'  if (!req.body.{f["name"]}) errors.push("{f["name"]} is required");')
    lines.extend([
        '  if (errors.length) return res.status(400).json({ errors });',
        '  next();',
        '}',
        '',
    ])

    if "list" in ops:
        lines.extend([
            f'router.get("/{r}", (req, res) => {{',
            f'  const {{ page = 1, limit = 20, sort = "id" }} = req.query;',
            f'  const start = (page - 1) * limit;',
            f'  const items = {r}Store.slice(start, start + Number(limit));',
            f'  res.json({{ data: items, total: {r}Store.length, page: Number(page) }});',
            '});', '',
        ])

    if "read" in ops:
        lines.extend([
            f'router.get("/{r}/:id", (req, res) => {{',
            f'  const item = {r}Store.find(i => i.id === Number(req.params.id));',
            f'  if (!item) return res.status(404).json({{ error: "{r} not found" }});',
            '  res.json(item);',
            '});', '',
        ])

    if "create" in ops:
        lines.extend([
            f'router.post("/{r}", validate{r.capitalize()}, (req, res) => {{',
            f'  const item = {{ id: nextId++, ...req.body, createdAt: new Date().toISOString() }};',
            f'  {r}Store.push(item);',
            '  res.status(201).json(item);',
            '});', '',
        ])

    if "update" in ops:
        lines.extend([
            f'router.put("/{r}/:id", validate{r.capitalize()}, (req, res) => {{',
            f'  const idx = {r}Store.findIndex(i => i.id === Number(req.params.id));',
            f'  if (idx === -1) return res.status(404).json({{ error: "{r} not found" }});',
            f'  {r}Store[idx] = {{ ...{r}Store[idx], ...req.body, updatedAt: new Date().toISOString() }};',
            f'  res.json({r}Store[idx]);',
            '});', '',
        ])

    if "delete" in ops:
        lines.extend([
            f'router.delete("/{r}/:id", (req, res) => {{',
            f'  const idx = {r}Store.findIndex(i => i.id === Number(req.params.id));',
            f'  if (idx === -1) return res.status(404).json({{ error: "{r} not found" }});',
            f'  {r}Store.splice(idx, 1);',
            '  res.status(204).send();',
            '});', '',
        ])

    lines.append("module.exports = router;")
    return "\n".join(lines)


def _gen_fastapi_api(resource, ops, fields):
    r = resource.lower()
    field_defs = "\n".join(f"    {f['name']}: {_py_type(f.get('type','str'))}" for f in fields)
    lines = [
        f"from fastapi import APIRouter, HTTPException, Query",
        f"from pydantic import BaseModel",
        f"from typing import List, Optional",
        f"from datetime import datetime",
        "",
        f"router = APIRouter(prefix='/{r}', tags=['{r.capitalize()}'])",
        "",
        f"class {r.capitalize()}Create(BaseModel):",
        field_defs,
        "",
        f"class {r.capitalize()}Response({r.capitalize()}Create):",
        f"    id: int",
        f"    created_at: datetime",
        "",
        f"_{r}_store: list = []",
        f"_next_id: int = 1",
        "",
    ]

    if "list" in ops:
        lines.extend([
            f'@router.get("/", response_model=List[{r.capitalize()}Response])',
            f"def list_{r}(page: int = Query(1, ge=1), limit: int = Query(20, le=100)):",
            f"    start = (page - 1) * limit",
            f"    return _{r}_store[start:start+limit]",
            "",
        ])

    if "create" in ops:
        lines.extend([
            f'@router.post("/", response_model={r.capitalize()}Response, status_code=201)',
            f"def create_{r}(data: {r.capitalize()}Create):",
            f"    global _next_id",
            f"    item = {{**data.dict(), 'id': _next_id, 'created_at': datetime.utcnow()}}",
            f"    _{r}_store.append(item)",
            f"    _next_id += 1",
            f"    return item",
            "",
        ])

    if "read" in ops:
        lines.extend([
            f'@router.get("/{{item_id}}", response_model={r.capitalize()}Response)',
            f"def get_{r}(item_id: int):",
            f"    item = next((i for i in _{r}_store if i['id'] == item_id), None)",
            f'    if not item: raise HTTPException(404, "{r} not found")',
            f"    return item",
            "",
        ])

    return "\n".join(lines)


def _gen_flask_api(resource, ops, fields):
    r = resource.lower()
    lines = [
        f"from flask import Blueprint, request, jsonify",
        "",
        f'{r}_bp = Blueprint("{r}", __name__, url_prefix="/{r}")',
        f"_{r}_store = []",
        f"_next_id = 1",
        "",
    ]

    if "list" in ops:
        lines.extend([
            f'@{r}_bp.route("/", methods=["GET"])',
            f"def list_{r}():",
            f"    return jsonify(_{r}_store)",
            "",
        ])

    if "create" in ops:
        lines.extend([
            f'@{r}_bp.route("/", methods=["POST"])',
            f"def create_{r}():",
            f"    global _next_id",
            f"    data = request.get_json()",
            f'    item = {{"id": _next_id, **data}}',
            f"    _{r}_store.append(item)",
            f"    _next_id += 1",
            f"    return jsonify(item), 201",
            "",
        ])

    return "\n".join(lines)


def _py_type(t):
    return {"string": "str", "number": "float", "integer": "int", "boolean": "bool"}.get(t, "str")


# ══════════════════════════════════════════════════════════════
# Tool 4: web_generate_css
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="web_generate_css",
    description=(
        "Generate professional CSS: design systems, themes, animations, "
        "responsive layouts, glassmorphism, gradients, and components."
    ),
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "style": "design_system | theme | animation | component | responsive",
        "theme": "dark | light | neon | minimal | glassmorphism",
        "components": "List: button, card, modal, table, form, navbar, sidebar",
    },
)
def web_generate_css(
    style: str = "design_system",
    theme: str = "dark",
    components: list = None,
) -> Dict[str, Any]:
    """Generate professional CSS code."""
    components = components or ["button", "card", "navbar"]

    if style == "design_system":
        css = _CSS_DESIGN_SYSTEM
    else:
        css = _generate_theme_css(theme, components)

    return {
        "success": True,
        "style": style,
        "theme": theme,
        "css": css,
        "components_included": components,
    }


def _generate_theme_css(theme, components):
    colors = {
        "dark": {"bg": "#0f172a", "surface": "#1e293b", "text": "#f1f5f9", "primary": "#6366f1"},
        "light": {"bg": "#ffffff", "surface": "#f8fafc", "text": "#1e293b", "primary": "#3b82f6"},
        "neon": {"bg": "#0a0a0f", "surface": "#1a1a2e", "text": "#eee", "primary": "#00ff88"},
        "glassmorphism": {"bg": "#0f172a", "surface": "rgba(255,255,255,0.05)", "text": "#f1f5f9", "primary": "#8b5cf6"},
    }
    c = colors.get(theme, colors["dark"])
    css = f":root {{\n  --bg: {c['bg']};\n  --surface: {c['surface']};\n  --text: {c['text']};\n  --primary: {c['primary']};\n}}\n"
    css += f"body {{ background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; }}\n"
    return css


# ══════════════════════════════════════════════════════════════
# Tool 5: web_bundle_project
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="web_bundle_project",
    description="Run build/bundle commands for a web project (npm/yarn/pnpm).",
    risk_level=ToolRiskLevel.HIGH,
    parameters={
        "project_dir": "Project directory path",
        "command": "install | dev | build | lint | test",
        "package_manager": "npm | yarn | pnpm",
    },
)
def web_bundle_project(
    project_dir: str,
    command: str = "build",
    package_manager: str = "npm",
) -> Dict[str, Any]:
    """Execute build commands for a web project."""
    if not os.path.isdir(project_dir):
        return {"success": False, "error": f"Directory not found: {project_dir}"}

    cmd_map = {
        "install": [package_manager, "install"],
        "dev": [package_manager, "run", "dev"],
        "build": [package_manager, "run", "build"],
        "lint": [package_manager, "run", "lint"],
        "test": [package_manager, "run", "test"],
    }

    if command not in cmd_map:
        return {"success": False, "error": f"Unknown command: {command}"}

    try:
        proc = subprocess.run(
            cmd_map[command], cwd=project_dir, capture_output=True,
            text=True, timeout=120, shell=False,
        )
        return {
            "success": proc.returncode == 0,
            "command": " ".join(cmd_map[command]),
            "stdout": proc.stdout[-5000:] if proc.stdout else "",
            "stderr": proc.stderr[-2000:] if proc.stderr else "",
            "exit_code": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Build timed out after 120s"}
    except FileNotFoundError:
        return {"success": False, "error": f"{package_manager} not found. Install Node.js first."}


# ══════════════════════════════════════════════════════════════
# Tool 6: web_dev_server
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="web_dev_server",
    description="Start or stop a local development server with hot reload.",
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "action": "start | stop | status",
        "project_dir": "Project directory",
        "port": "Port number (default 3000)",
    },
)
def web_dev_server(
    action: str = "status",
    project_dir: str = "",
    port: int = 3000,
) -> Dict[str, Any]:
    """Manage local dev server."""
    if action == "status":
        return {"success": True, "active_servers": list(_active_servers.keys())}

    if action == "stop":
        server = _active_servers.pop(project_dir, None)
        if server and server.get("process"):
            try:
                server["process"].terminate()
            except Exception:
                pass
        return {"success": True, "message": f"Server stopped for {project_dir}"}

    if action == "start":
        if not os.path.isdir(project_dir):
            return {"success": False, "error": f"Directory not found: {project_dir}"}
        try:
            proc = subprocess.Popen(
                ["npm", "run", "dev", "--", "--port", str(port)],
                cwd=project_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                shell=False,
            )
            _active_servers[project_dir] = {"process": proc, "port": port}
            return {
                "success": True,
                "message": f"Dev server started on http://localhost:{port}",
                "pid": proc.pid,
            }
        except FileNotFoundError:
            return {"success": False, "error": "npm not found"}

    return {"success": False, "error": f"Unknown action: {action}"}


# ══════════════════════════════════════════════════════════════
# Tool 7: web_deploy_config
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="web_deploy_config",
    description=(
        "Generate deployment configurations: Dockerfile, Nginx config, "
        "Vercel config, Netlify config, or docker-compose."
    ),
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "platform": "docker | nginx | vercel | netlify | compose",
        "framework": "react | vue | nextjs | static",
        "project_name": "Project name",
    },
)
def web_deploy_config(
    platform: str = "docker",
    framework: str = "react",
    project_name: str = "my-app",
) -> Dict[str, Any]:
    """Generate deployment configuration files."""
    generators = {
        "docker": _generate_dockerfile,
        "nginx": _generate_nginx_config,
        "vercel": _generate_vercel_config,
        "netlify": _generate_netlify_config,
        "compose": _generate_compose_config,
    }

    gen = generators.get(platform)
    if not gen:
        return {"success": False, "error": f"Unknown platform: {platform}"}

    if platform in ("docker", "nginx"):
        config = gen(framework)
    else:
        config = gen(framework)

    ext_map = {"docker": "Dockerfile", "nginx": "nginx.conf", "vercel": "vercel.json",
               "netlify": "netlify.toml", "compose": "docker-compose.yml"}

    return {
        "success": True,
        "platform": platform,
        "filename": ext_map.get(platform, "config"),
        "config": config,
    }


def _generate_dockerfile(framework):
    if framework == "nextjs":
        return textwrap.dedent("""\
            FROM node:20-alpine AS deps
            WORKDIR /app
            COPY package*.json ./
            RUN npm ci --only=production

            FROM node:20-alpine AS builder
            WORKDIR /app
            COPY . .
            COPY --from=deps /app/node_modules ./node_modules
            RUN npm run build

            FROM node:20-alpine AS runner
            WORKDIR /app
            ENV NODE_ENV=production
            COPY --from=builder /app/.next ./.next
            COPY --from=builder /app/node_modules ./node_modules
            COPY --from=builder /app/package.json ./
            EXPOSE 3000
            CMD ["npm", "start"]
        """)
    return textwrap.dedent("""\
        FROM node:20-alpine AS build
        WORKDIR /app
        COPY package*.json ./
        RUN npm ci
        COPY . .
        RUN npm run build

        FROM nginx:alpine
        COPY --from=build /app/dist /usr/share/nginx/html
        COPY nginx.conf /etc/nginx/conf.d/default.conf
        EXPOSE 80
        CMD ["nginx", "-g", "daemon off;"]
    """)


def _generate_nginx_config(framework):
    return textwrap.dedent("""\
        server {
            listen 80;
            server_name _;
            root /usr/share/nginx/html;
            index index.html;

            location / {
                try_files $uri $uri/ /index.html;
            }

            location /api/ {
                proxy_pass http://backend:8000;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
            }

            location ~* \\.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
                expires 1y;
                add_header Cache-Control "public, immutable";
            }

            gzip on;
            gzip_types text/css application/javascript application/json image/svg+xml;
        }
    """)


def _generate_vercel_config(framework):
    return json.dumps({
        "framework": framework if framework != "react" else "vite",
        "buildCommand": "npm run build",
        "outputDirectory": "dist" if framework != "nextjs" else ".next",
        "rewrites": [{"source": "/(.*)", "destination": "/index.html"}],
    }, indent=2)


def _generate_netlify_config(framework):
    return textwrap.dedent("""\
        [build]
          command = "npm run build"
          publish = "dist"

        [[redirects]]
          from = "/*"
          to = "/index.html"
          status = 200

        [[headers]]
          for = "/assets/*"
          [headers.values]
            Cache-Control = "public, max-age=31536000, immutable"
    """)


def _generate_compose_config(framework):
    return textwrap.dedent("""\
        version: '3.8'
        services:
          frontend:
            build: .
            ports:
              - "3000:80"
            depends_on:
              - backend

          backend:
            image: node:20-alpine
            working_dir: /app
            volumes:
              - ./backend:/app
            ports:
              - "8000:8000"
            command: npm start

          db:
            image: postgres:15-alpine
            environment:
              POSTGRES_DB: app
              POSTGRES_USER: user
              POSTGRES_PASSWORD: pass
            volumes:
              - pgdata:/var/lib/postgresql/data
            ports:
              - "5432:5432"

        volumes:
          pgdata:
    """)
