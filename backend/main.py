"""
Custom LLM System — Main Entry Point
─────────────────────────────────────
Universal AI Agent — Multi-Model Provider System

Supports:
  - Gemini (Google)    — set GEMINI_API_KEY
  - Claude (Anthropic) — set CLAUDE_API_KEY
  - ChatGPT (OpenAI)   — set OPENAI_API_KEY

Usage:
    python main.py                          # Start API server (auto-detect provider)
    python main.py --chat                   # Interactive chat (auto-detect)
    python main.py --chat --provider claude # Chat with Claude
    python main.py --chat --provider chatgpt # Chat with ChatGPT
    python main.py --providers              # List available providers
    python main.py --evolve "sort a list"   # Generate optimal code via RLHF
    python main.py --nightwatch             # Start proactive background daemon
    python main.py --audit main.py          # Run Threat Hunter security audit
    python main.py --transpile legacy/ --target-lang rust # Run Reverse Transpiler
    
    # Universal Domain Features
    python main.py --board-meeting plan.pdf # Devil's Advocate Risk Matrix
    python main.py --tutor "Quantum Physics" # Socratic Auto-Tutor
    python main.py --syndicate draft.txt    # Content Factory Syndication
    python main.py --organize ~/Downloads   # Digital Estate Archivist
    python main.py --contract-audit nda.pdf # Toxic Clause Hunter
"""

import argparse
import logging
import os
import shutil
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)

# Module-level app state — replaces builtins hack
_app_state = {"registry": None}


def _ensure_env_file() -> None:
    """Copy .env.example → .env if .env is missing, and warn if no provider key is set."""
    env_file = Path(__file__).parent / ".env"
    env_example = Path(__file__).parent / ".env.example"

    if not env_file.exists():
        if env_example.exists():
            shutil.copy(env_example, env_file)
            logger.warning(
                "⚠️  No .env file found — copied .env.example to .env. "
                "Edit backend/.env and add your API keys to activate an LLM provider."
            )
        else:
            logger.warning(
                "⚠️  No .env file found and .env.example is missing. "
                "Set GEMINI_API_KEY, CLAUDE_API_KEY, or OPENAI_API_KEY to use an LLM provider."
            )

    # Log which provider key is active (informational)
    active = [
        name
        for name, var in [
            ("Gemini", "GEMINI_API_KEY"),
            ("Claude", "CLAUDE_API_KEY"),
            ("OpenAI", "OPENAI_API_KEY"),
        ]
        if os.getenv(var)
    ]
    if active:
        logger.info("✅ LLM provider keys detected: %s", ", ".join(active))
    else:
        logger.warning(
            "⚠️  No LLM provider API key detected (GEMINI_API_KEY / CLAUDE_API_KEY / OPENAI_API_KEY). "
            "The local Mistral 7B fallback will be used if available."
        )


def setup_logging(level: str = "INFO"):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s │ %(name)-25s │ %(levelname)-5s │ %(message)s",
        datefmt="%H:%M:%S",
    )
    # Reduce noise from libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def create_provider_registry(provider: str = "auto", api_key: str = None, base_url: str = None):
    """
    Create and configure the provider registry.
    """
    from core.model_providers import ProviderRegistry
    from config.settings import provider_config
    if api_key:
        provider_config.api_key = api_key
    if base_url:
        provider_config.base_url = base_url
    
    registry = ProviderRegistry.auto_detect()
    return registry


def show_banner(registry=None):
    """Show the startup banner with provider info."""
    provider_info = ""
    if registry and registry.active:
        p = registry.active
        provider_info = f"   Provider: {p.name.upper()} ({p.model})"
    else:
        provider_info = "   Provider: NONE DETECTED"

    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   🧠  Universal AI Agent  v2.0                               ║
    ║   ──────────────────────────                                 ║
    ║   Multi-Model • Multi-Domain • Multi-Persona                 ║
    ║                                                              ║
    ║   Models:                                                    ║
    ║     🟢 Gemini (Google)     — GEMINI_API_KEY                  ║
    ║     🟣 Claude (Anthropic)  — CLAUDE_API_KEY                  ║
    ║     🔵 ChatGPT (OpenAI)   — OPENAI_API_KEY                  ║
    ║                                                              ║
    ║   {provider_info:<59}║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)


def start_server(provider: str = "auto", api_key: str = None, base_url: str = None):
    """Start the FastAPI server."""
    import uvicorn
    from config.settings import api_config

    _ensure_env_file()

    registry = create_provider_registry(provider, api_key, base_url)
    show_banner(registry)

    # Store registry for the API server to pick up
    _app_state["registry"] = registry
    
    # 🪖 ENGAGE ARMY DEFENSE MATRIX (Rule 4)
    try:
        from agents.justice.army import army_command
        army_command.patrol_perimeter()
    except Exception as e:
        logger.warning(f"Failed to boot Army Agent Defense Matrix: {e}")

    uvicorn_kwargs = {
        "host": api_config.host,
        "port": api_config.port,
        "reload": api_config.reload,
        "workers": api_config.workers,
        "log_level": "info",
    }

    # ── HTTPS / TLS Support ──
    from config.settings import ssl_config
    if ssl_config.is_ready:
        uvicorn_kwargs["ssl_keyfile"] = ssl_config.keyfile
        uvicorn_kwargs["ssl_certfile"] = ssl_config.certfile
        logger.info(f"🔒 HTTPS enabled with cert={ssl_config.certfile}")
    else:
        logger.info("🔓 Running in HTTP mode (set SSL_ENABLED=1 and provide certs for HTTPS)")

    uvicorn.run("api.server:app", **uvicorn_kwargs)


def interactive_chat(provider: str = "auto", api_key: str = None, base_url: str = None):
    """Run interactive chat in the terminal with any model provider."""
    from agents.controller import AgentController

    registry = create_provider_registry(provider, api_key, base_url)
    show_banner(registry)

    print(registry.status_display())

    # Get the generate function from the registry
    generate_fn = registry.generate_fn()

    print("\n🤖 Initializing agent...")
    agent = AgentController(generate_fn=generate_fn)

    active = registry.active
    model_name = f"{active.name}/{active.model}" if active else "none"

    # Pre-authorize device control if the user wants it in this session
    from agents.tools.device_ops import SecurityGateway
    print("\n🛡️ [SECURITY PROTOCOL] The agent supports Host Device Management (Process/Hardware Control).")
    allow_device = input("   Do you want to grant Device Control permissions for this session? (y/N): ").strip().lower()
    if allow_device in ['y', 'yes', 'true']:
        SecurityGateway._DEVICE_CONTROL_GRANTED = True
        print("   ✅ Device Control GRANTED.")
    else:
        print("   ❌ Device Control DENIED.")

    print(f"\n{'═' * 60}")
    print(f"  💬 Interactive Chat — Model: {model_name}")
    print("  Commands:")
    print("    /think     — Force thinking loop")
    print("    /stats     — Show memory stats")
    print("    /reset     — Clear conversation")
    print("    /provider  — Show active provider")
    print("    /model X   — Set target model X")
    print("    /models    — List all available providers")
    print(f"{'═' * 60}\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "/quit"):
                print("\nGoodbye! 👋")
                break

            # ── Special commands ──
            if user_input == "/stats":
                stats = agent.get_stats()
                print(f"\n📊 Stats: {stats}\n")
                continue

            if user_input == "/reset":
                agent.reset_conversation()
                print("🔄 Conversation cleared.\n")
                continue

            if user_input == "/provider":
                if registry.active:
                    p = registry.active
                    stats = p.get_stats()
                    print(f"\n🔌 Active: {p.name} ({p.model})")
                    print(f"   Calls: {stats['calls']} | Errors: {stats['errors']}")
                    if stats['calls'] > 0:
                        print(f"   Avg latency: {stats['avg_latency_ms']:.0f}ms")
                    print()
                continue

            if user_input == "/models":
                print(f"\n{registry.status_display()}\n")
                for info in registry.list_providers():
                    status = "🟢 ACTIVE" if info["active"] else "⚪ ready"
                    print(f"  {status}  {info['name']:<10} {info['model']}")
                print()
                continue

            if user_input.startswith("/model"):
                parts = user_input.split()
                if len(parts) < 2:
                    print("Usage: /model <model_name>\\n")
                    continue
                target = parts[1]
                from config.settings import provider_config
                provider_config.model = target
                print(f"\\n🔄 Model target updated to: {target} (will apply on next restart)\\n")
                continue


            # ── Normal message processing ──
            use_thinking = user_input.startswith("/think")
            if use_thinking:
                user_input = user_input[6:].strip()
                
            # 🪖 Check Army Perimeter before processing input (Rule 4)
            try:
                from agents.justice.army import army_command
                if not army_command.patrol_perimeter():
                    print("\n🪖 [SYSTEM LOCKDOWN] The Army Agent has detected a system compromise.")
                    print("Execution halted for safety.")
                    continue
            except Exception:
                pass

            print("\n🧠 Thinking...")
            result = agent.process(
                user_input=user_input,
                use_thinking_loop=use_thinking,
            )

            print(f"\nAssistant: {result.answer}")
            print(
                f"\n  ⎡ confidence={result.confidence:.3f} | "
                f"mode={result.mode} | "
                f"provider={registry.active_name} | "
                f"{result.duration_ms:.0f}ms ⎤\n"
            )

        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


def list_providers():
    """Show all available model providers."""
    registry = create_provider_registry()
    print(f"\\n{registry.status_display()}")
    

    from config.settings import provider_config
    if not provider_config.is_configured:
        print("  💡 No API key detected! Set environment variables:")
        print("     set LLM_API_KEY=your-key")
        print("     set LLM_BASE_URL=https://api.openai.com/v1 (optional)")
        print("     set LLM_MODEL=gpt-4o (optional)")
        print()
def run_evolution(prompt: str, provider: str = "auto", api_key: str = None, base_url: str = None):
    """Run the Code Evolution Engine."""
    from core.model_providers import create_provider_registry
    from brain.evolution import CodeEvolutionEngine
    
    registry = create_provider_registry(provider, api_key, base_url)
    if not registry.active:
        print("❌ No active provider found. Please set API keys.")
        return
        
    print(f"\n🧬 Initializing Code Evolution Engine ({registry.active.name})")
    engine = CodeEvolutionEngine(registry)
    
    # We use a default set of test cases for benchmarking if not provided
    test_cases = "if __name__ == '__main__':\n    pass # Mock test"
    
    best = engine.evolve(prompt, test_cases, generations=3)
    if best:
        print("\n" + "=" * 60)
        print("    ✨ OPTIMIZED CODE ✨")
        print("=" * 60)
        print(best.code)
        print("=" * 60 + "\n")

def start_night_watch(provider: str = "auto", api_key: str = None, base_url: str = None):
    """Start the Night Watch Daemon."""
    from core.model_providers import create_provider_registry
    from agents.controller import AgentController
    from agents.proactive.night_watch import NightWatchDaemon
    
    registry = create_provider_registry(provider, api_key, base_url)
    if not registry.active:
        print("❌ No active provider found. Night Watch cannot start.")
        return
        
    print(f"\n🌙 Initializing Night Watch Daemon ({registry.active.name})")
    
    agent = AgentController(generate_fn=registry.generate_fn())
    daemon = NightWatchDaemon(agent)
    
    # Actually block and wait for 02:00 locally, or we can just trigger it once for testing
    print("Triggering an immediate audit for demonstration purposes...\n")
    daemon.run_nightly_audit()


def run_threat_hunter(file_path: str, provider: str = "auto", api_key: str = None, base_url: str = None):
    """Run a security audit on a file."""
    from core.model_providers import create_provider_registry
    from agents.controller import AgentController
    from agents.profiles.threat_hunter import ThreatHunter
    
    registry = create_provider_registry(provider, api_key, base_url)
    if not registry.active:
        print("❌ No active provider found. Threat Hunter cannot start.")
        return
        
    print(f"\n🕵️ Initializing Threat Hunter ({registry.active.name})")
    
    agent = AgentController(generate_fn=registry.generate_fn())
    hunter = ThreatHunter(agent)
    
    result = hunter.audit_file(file_path)
    hunter.write_audit_report(result)
    print("\n" + "=" * 60)
    print(result.answer)
    print("=" * 60 + "\n")


def run_swarm_defense():
    """Deploy the Active Defense Swarm Matrix."""
    from agents.proactive.swarm_defense import SwarmMatrix
    matrix = SwarmMatrix()
    matrix.deploy()


def run_transpile(source_dir: str, target_lang: str, provider: str = "auto", api_key: str = None, base_url: str = None):
    """Run the Reverse-Engineering Code Transpiler."""
    from core.model_providers import create_provider_registry
    from agents.controller import AgentController
    from brain.transpiler import ReverseTranspiler
    
    registry = create_provider_registry(provider, api_key, base_url)
    if not registry.active:
        print("❌ No active provider found. Transpiler cannot start.")
        return
        
    print(f"\n🔄 Initializing Migration Engine ({registry.active.name})")
    
    agent = AgentController(generate_fn=registry.generate_fn())
    transpiler = ReverseTranspiler(agent)
    
    transpiler.transpile_directory(source_dir, target_lang)


def run_devils_advocate(file_path: str, provider: str = "auto", api_key: str = None, base_url: str = None):
    from core.model_providers import create_provider_registry
    from agents.controller import AgentController
    from agents.profiles.devils_advocate import DevilsAdvocate
    registry = create_provider_registry(provider, api_key, base_url)
    if not registry.active: return
    print(f"\n👔 Assembling the Board of Directors ({registry.active.name})")
    agent = AgentController(generate_fn=registry.generate_fn())
    board = DevilsAdvocate(agent)
    result = board.audit_business_plan(file_path)
    print("\n" + "=" * 60 + "\n" + result.answer + "\n" + "=" * 60 + "\n")

def run_socratic_tutor(topic: str, provider: str = "auto", api_key: str = None, base_url: str = None):
    from core.model_providers import create_provider_registry
    from agents.controller import AgentController
    from agents.profiles.expert_tutor import ExpertTutorEngine
    registry = create_provider_registry(provider, api_key, base_url)
    if not registry.active: return
    agent = AgentController(generate_fn=registry.generate_fn())
    tutor = ExpertTutorEngine(generate_fn=registry.generate_fn(), agent_controller=agent)
    tutor.start_interactive(topic)

def run_content_factory(file_path: str, provider: str = "auto", api_key: str = None, base_url: str = None):
    from core.model_providers import create_provider_registry
    from agents.controller import AgentController
    from brain.content_factory import ContentFactory
    registry = create_provider_registry(provider, api_key, base_url)
    if not registry.active: return
    agent = AgentController(generate_fn=registry.generate_fn())
    factory = ContentFactory(agent)
    factory.syndicate_content(file_path)

def run_archivist(target_dir: str, provider: str = "auto", api_key: str = None, base_url: str = None):
    from core.model_providers import create_provider_registry
    from agents.controller import AgentController
    from agents.proactive.archivist import DigitalArchivist
    registry = create_provider_registry(provider, api_key, base_url)
    if not registry.active: return
    agent = AgentController(generate_fn=registry.generate_fn())
    archivist = DigitalArchivist(agent)
    archivist.organize_directory(target_dir)

def run_contract_hunter(file_path: str, provider: str = "auto", api_key: str = None, base_url: str = None):
    from core.model_providers import create_provider_registry
    from agents.controller import AgentController
    from agents.profiles.contract_hunter import ContractHunter
    registry = create_provider_registry(provider, api_key, base_url)
    if not registry.active: return
    agent = AgentController(generate_fn=registry.generate_fn())
    hunter = ContractHunter(agent)
    hunter.audit_contract(file_path)


def run_deep_researcher(topic: str, provider: str = "auto", api_key: str = None, base_url: str = None):
    from agents.controller import AgentController
    from agents.profiles.deep_researcher import DeepWebResearcher
    registry = create_provider_registry(provider, api_key, base_url)
    if not registry.active: return
    agent = AgentController(generate_fn=registry.generate_fn())
    researcher = DeepWebResearcher(agent)
    researcher.compile_dossier(topic)


def run_multi_agent_debate(topic: str, provider: str = "auto", api_key: str = None, base_url: str = None):
    from core.model_providers import create_provider_registry
    from agents.controller import AgentController
    from agents.profiles.multi_agent_orchestrator import MultiAgentOrchestrator
    
    registry = create_provider_registry(provider, api_key, base_url)
    if not registry.active:
        print("❌ No active provider found. Debate cannot start.")
        return
        
    print(f"\n🤝 Initializing Multi-Agent Debate ({registry.active.name})")
    
    agent = AgentController(generate_fn=registry.generate_fn())
    orchestrator = MultiAgentOrchestrator(agent)
    
    result = orchestrator.orchestrate_debate(topic)
    print("\n" + "=" * 60)
    print(result.answer)
    print("=" * 60 + "\n")


def run_agent_orchestrator(task: str, strategy: str = "auto", provider: str = "auto", api_key: str = None, base_url: str = None):
    from core.model_providers import create_provider_registry
    from agents.orchestrator import AgentOrchestrator, OrchestratorStrategy
    
    registry = create_provider_registry(provider, api_key, base_url)
    if not registry.active:
        print("❌ No active provider found. Orchestrator cannot start.")
        return
        
    try:
        strat_enum = OrchestratorStrategy(strategy.lower())
    except ValueError:
        print(f"⚠️ Unknown strategy '{strategy}', defaulting to 'auto'")
        strat_enum = OrchestratorStrategy.AUTO

    print(f"\n🎭 Initializing Agent Orchestrator ({registry.active.name}) — Strategy: {strat_enum.value.upper()}")
    
    orchestrator = AgentOrchestrator(generate_fn=registry.generate_fn())
    orchestrator.start_interactive(task)


def run_devops_reviewer(issue: str, repo_path: str, provider: str = "auto", api_key: str = None, base_url: str = None):
    from core.model_providers import create_provider_registry
    from agents.controller import AgentController
    from agents.profiles.devops_reviewer import DevOpsReviewer
    
    registry = create_provider_registry(provider, api_key, base_url)
    if not registry.active:
        print("❌ No active provider found. DevOps Reviewer cannot start.")
        return
        
    print(f"\n🛠️ Initializing DevOps Reviewer ({registry.active.name})")
    
    agent = AgentController(generate_fn=registry.generate_fn())
    reviewer = DevOpsReviewer(agent)
    
    result = reviewer.autonomous_fix(issue, repo_path)
    print("\n" + "=" * 60)
    print(result.answer)
    print("=" * 60 + "\n")

def run_aesce_dream_state(provider: str = "auto", api_key: str = None, base_url: str = None):
    """Universal Feature: Trigger the Auto-Evolution (AESCE) Engine."""
    import os
    from core.model_providers import ProviderRegistry
    
    print(f"\n[INFO] Initializing Synthesized Consciousness Engine using provider '{provider}'...")
    registry = ProviderRegistry()
    if api_key:
        os.environ["LLM_API_KEY"] = api_key
        
    from brain.memory import MemoryManager
    from brain.aesce import SynthesizedConsciousnessEngine
    
    memory = MemoryManager()
    engine = SynthesizedConsciousnessEngine(memory, registry.generate_fn())
    
    try:
        engine.trigger_dream_state()
    except KeyboardInterrupt:
        print("\n[INFO] Dream State interrupted by user.")

def run_swarm_task(task: str, provider: str = "auto", api_key: str = None, base_url: str = None):
    """Run Multi-Agent Swarm Intelligence on a complex task."""
    from agents.profiles.swarm_intelligence import SwarmOrchestrator
    registry = create_provider_registry(provider, api_key, base_url)
    if not registry.active:
        return
    from agents.controller import AgentController
    agent = AgentController(generate_fn=registry.generate_fn())
    swarm = SwarmOrchestrator(generate_fn=registry.generate_fn(), agent_controller=agent)
    swarm.start_interactive(task)

def run_multimodal_analysis(file_path: str, provider: str = "auto", api_key: str = None, base_url: str = None):
    """Analyze a file using the Multimodal Pipeline (images, PDFs, audio, code)."""
    from brain.multimodal import MultimodalBrain
    from pathlib import Path
    registry = create_provider_registry(provider, api_key, base_url)
    if not registry.active:
        return
    brain = MultimodalBrain(generate_fn=registry.generate_fn())
    path = Path(file_path)
    if not path.exists():
        print(f"❌ File not found: {file_path}")
        return
    print(f"\n🧠 Analyzing: {path.name}")
    result = brain.process(file_path)
    print(f"Modality: {result.modality}")
    print(f"\n{result.analysis}")


def run_threat_scan(target_path: str):
    """Scan a file or directory for threats and offer remediation."""
    from pathlib import Path
    from agents.safety.threat_scanner import ThreatScanner

    try:
        from config.settings import threat_config
        scanner = ThreatScanner(
            quarantine_dir=threat_config.quarantine_dir,
            entropy_threshold=threat_config.entropy_threshold,
            max_file_size_mb=threat_config.max_file_size_mb,
        )
    except Exception:
        scanner = ThreatScanner()

    path = Path(target_path).resolve()
    if not path.exists():
        print(f"❌ Path not found: {target_path}")
        return

    # Collect files to scan
    files = [path] if path.is_file() else list(path.rglob("*"))
    files = [f for f in files if f.is_file()]

    print(f"\n🛡️  Threat Scanner — Scanning {len(files)} file(s)...")
    print("═" * 60)

    threats = []
    for i, file in enumerate(files, 1):
        print(f"  [{i}/{len(files)}] Scanning: {file.name}...", end=" ")
        report = scanner.scan_file(str(file))
        if report.is_threat:
            sev = report.severity
            emoji = sev.emoji if sev else "⚠️"
            print(f"{emoji} THREAT — {report.threat_type.value.upper() if report.threat_type else 'UNKNOWN'}")
            threats.append(report)
        else:
            print("✅ Clean")

    print("\n" + "═" * 60)

    if not threats:
        print("  ✅ ALL FILES CLEAN — No threats detected.")
        print(f"  📊 Scanned: {len(files)} files | Threats: 0")
        print("═" * 60 + "\n")
        return

    # Show threat details
    print(f"  🚨 THREATS FOUND: {len(threats)} / {len(files)} files")
    print("═" * 60)
    for report in threats:
        print(report.detailed_report())
        print()

    # Ask user for approval
    print("\n🔒 REMEDIATION OPTIONS:")
    print("  [1] QUARANTINE — Move threats to secure vault")
    print("  [2] DESTROY    — Permanently delete threats (3-pass secure overwrite)")
    print("  [3] SKIP       — Take no action")
    choice = input("\n  Select action (1/2/3): ").strip()

    if choice == "1":
        print("\n🔒 Quarantining threats...")
        for report in threats:
            result = scanner.quarantine(report)
            if result["success"]:
                print(f"  ✅ Quarantined: {Path(report.target).name}")
            else:
                print(f"  ❌ Failed: {result.get('error', 'Unknown error')}")
        print("\n  🔒 All threats quarantined.")

    elif choice == "2":
        confirm = input("\n  ⚠️  This is IRREVERSIBLE. Type 'DESTROY' to confirm: ").strip()
        if confirm == "DESTROY":
            print("\n🔥 Destroying threats...")
            for report in threats:
                result = scanner.destroy(report)
                if result["success"]:
                    proof = result["destruction_proof"]
                    print(f"  🔥 Destroyed: {Path(report.target).name}")
                    print(f"     Proof: {proof['proof_hash'][:24]}...")
                else:
                    print(f"  ❌ Failed: {result.get('error', 'Unknown error')}")
            print("\n  🔥 All threats destroyed. Cryptographic proof generated.")
        else:
            print("  Destruction cancelled.")

    else:
        print("  ⚠️  No action taken. Threats remain on disk.")

    print("═" * 60 + "\n")

def run_mcp_server(transport: str = "stdio", port: int = 8080):
    """Run the FastMCP server."""
    from mcp_server.server import create_mcp_server
    
    logger.info(f"Starting MCP server on {transport} transport...")
    server = create_mcp_server()
    
    if transport == "stdio":
        server.run(transport="stdio")
    else:
        server.run(transport="streamable-http", port=port)

def main():
    parser = argparse.ArgumentParser(
        description="Universal AI Agent — Multi-Model Provider System"
    )
    parser.add_argument(
        "--chat", action="store_true",
        help="Start interactive chat mode"
    )
    parser.add_argument(
        "--provider", type=str, default="auto",
        help="Ignored. Setup for backwards compatibility."
    )
    parser.add_argument(
        "--base-url", type=str, default=None,
        help="Base URL for the Universal LLM provider"
    )
    parser.add_argument(
        "--api-key", type=str, default=None,
        help="API key for the chosen provider"
    )
    parser.add_argument(
        "--providers", action="store_true",
        help="List all available model providers"
    )
    parser.add_argument(
        "--evolve", type=str, default=None,
        help="Run Code Evolution Engine on a prompt"
    )
    parser.add_argument(
        "--nightwatch", action="store_true",
        help="Start the proactive Night Watch background daemon"
    )
    parser.add_argument(
        "--audit", type=str, default=None,
        help="Run Threat Hunter security audit on a specific file"
    )
    parser.add_argument(
        "--transpile", type=str, default=None,
        help="Directory of legacy code to reverse engineer and transpile"
    )
    parser.add_argument(
        "--target-lang", type=str, default="python",
        help="Target language for transpilation (e.g., rust, go, python, typescript)"
    )
    
    # Universal Domain Features
    parser.add_argument(
        "--board-meeting", type=str, default=None,
        help="Run Devil's Advocate against a business document"
    )
    parser.add_argument(
        "--tutor", type=str, default=None,
        help="Start a Socratic Auto-Tutor session on a given topic"
    )
    parser.add_argument(
        "--syndicate", type=str, default=None,
        help="Run the Content Factory syndication pipeline on a text file"
    )
    parser.add_argument(
        "--organize", type=str, default=None,
        help="Run Digital Archivist on a messy directory"
    )
    parser.add_argument(
        "--contract-audit", type=str, default=None,
        help="Review and modify legal contracts to find toxic or predatory clauses."
    )
    
    # === Swarm Defense Matrix ===
    parser.add_argument(
        "--deploy-swarm",
        action="store_true",
        help="Deploy the Active Defense Swarm (Honeypots and Tarpits) to protect the system."
    )
    
    # === Deep Intel Hub ===
    parser.add_argument(
        "--deep-research", type=str, default=None,
        help="Run the Deep Web Intelligence Bot to compile a dossier on a given topic."
    )
    
    # === Multi-Agent Orchestrator ===
    parser.add_argument(
        "--collaborate", type=str, default=None,
        help="Run a Multi-Agent Debate on a specific topic or problem."
    )
    
    # === NEW: Production Agent Orchestrator ===
    parser.add_argument(
        "--orchestrate", type=str, default=None,
        help="Run the advanced Agent Orchestrator on a complex task"
    )
    parser.add_argument(
        "--strategy", type=str, default="auto",
        choices=["auto", "swarm", "pipeline", "hierarchy", "debate"],
        help="Orchestration strategy to use"
    )
    
    # === DevOps PR Reviewer ===
    parser.add_argument(
        "--devops", type=str, default=None,
        help="Propose an autonomous fix for a given issue."
    )
    parser.add_argument(
        "--repo-path", type=str, default=".",
        help="Target repository path for the DevOps reviewer (default current directory)."
    )
    
    # === AESCE Engine ===
    parser.add_argument(
        "--aesce", action="store_true",
        help="Trigger the Auto-Evolution & Synthesized Consciousness Engine (Dream State)."
    )
    
    # === Multi-Agent Swarm Intelligence ===
    parser.add_argument(
        "--swarm", type=str, default=None,
        help="Deploy Multi-Agent Swarm Intelligence on a complex task."
    )
    
    # === Multimodal Analysis ===
    parser.add_argument(
        "--analyze", type=str, default=None,
        help="Analyze a file using the Multimodal Pipeline (images, PDFs, audio)."
    )
    
    # === Threat Scanner ===
    parser.add_argument(
        "--scan", type=str, default=None,
        help="Scan a file or directory for viruses, malware, and threats."
    )
    
    # === MCP Server ===
    parser.add_argument(
        "--mcp", action="store_true",
        help="Start the MCP (Model Context Protocol) server"
    )
    parser.add_argument(
        "--mcp-transport", type=str, default="stdio",
        choices=["stdio", "http"],
        help="MCP transport protocol (default: stdio)"
    )
    parser.add_argument(
        "--mcp-port", type=int, default=8080,
        help="MCP HTTP transport port (default: 8080)"
    )
    
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )

    args = parser.parse_args()
    setup_logging(args.log_level)

    if args.deploy_swarm:
        run_swarm_defense()
    elif args.evolve:
        run_evolution(args.evolve, provider=args.provider, api_key=args.api_key)
    elif args.nightwatch:
        start_night_watch(provider=args.provider, api_key=args.api_key)
    elif args.audit:
        run_threat_hunter(args.audit, provider=args.provider, api_key=args.api_key)
    elif args.transpile:
        run_transpile(args.transpile, args.target_lang, provider=args.provider, api_key=args.api_key)
    elif args.board_meeting:
        run_devils_advocate(args.board_meeting, provider=args.provider, api_key=args.api_key)
    elif args.tutor:
        run_socratic_tutor(args.tutor, provider=args.provider, api_key=args.api_key)
    elif args.syndicate:
        run_content_factory(args.syndicate, provider=args.provider, api_key=args.api_key)
    elif args.deep_research:
        run_deep_researcher(args.deep_research, provider=args.provider, api_key=args.api_key)
    elif args.organize:
        run_archivist(args.organize, provider=args.provider, api_key=args.api_key)
    elif args.contract_audit:
        run_contract_hunter(args.contract_audit, provider=args.provider, api_key=args.api_key)
    elif args.orchestrate:
        run_agent_orchestrator(args.orchestrate, strategy=args.strategy, provider=args.provider, api_key=args.api_key)
    elif args.collaborate:
        run_multi_agent_debate(args.collaborate, provider=args.provider, api_key=args.api_key)
    elif args.devops:
        run_devops_reviewer(args.devops, repo_path=args.repo_path, provider=args.provider, api_key=args.api_key)
    elif args.aesce:
        run_aesce_dream_state(provider=args.provider, api_key=args.api_key)
    elif args.swarm:
        run_swarm_task(args.swarm, provider=args.provider, api_key=args.api_key)
    elif args.analyze:
        run_multimodal_analysis(args.analyze, provider=args.provider, api_key=args.api_key)
    elif args.scan:
        run_threat_scan(args.scan)
    elif args.mcp:
        run_mcp_server(transport=args.mcp_transport, port=args.mcp_port)
    elif args.providers:
        list_providers()
    elif args.chat:
        interactive_chat(provider=args.provider, api_key=args.api_key, base_url=args.base_url)
    else:
        start_server(provider=args.provider, api_key=args.api_key, base_url=args.base_url)


if __name__ == "__main__":
    main()
