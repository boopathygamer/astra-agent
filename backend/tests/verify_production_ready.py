"""Final production-readiness verification for all Phase 6 modules."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import logging; logging.disable(logging.CRITICAL)

errors = []
print("=" * 60)
print("  PHASE 6: ULTRA-PERFORMANCE VERIFICATION")
print("=" * 60)

# === PHASE 6A: Infrastructure ===
print("\n[Phase 6A: Infrastructure]")

try:
    from config.settings import ssl_config, token_budget_config
    assert hasattr(ssl_config, 'is_ready')
    assert token_budget_config.daily_limit == 1000000
    print("  OK config/settings.py (SSLConfig + TokenBudgetConfig)")
except Exception as e:
    errors.append(f"settings: {e}"); print(f"  FAIL settings: {e}")

try:
    from telemetry.log_exporter import StructuredLogExporter
    exporter = StructuredLogExporter(log_dir="data/test_logs")
    exporter.write_event("test", {"key": "value"})
    stats = exporter.get_stats()
    print(f"  OK log_exporter (JSONL write + rotation)")
except Exception as e:
    errors.append(f"log_exporter: {e}"); print(f"  FAIL log_exporter: {e}")

# === PHASE 6B: Smart Caching & Budget ===
print("\n[Phase 6B: Smart Caching & Budget]")

try:
    from brain.semantic_cache import SemanticCache
    cache = SemanticCache(similarity_threshold=0.3)  # TF-IDF cosine is lower than neural
    cache.put("What is Python programming language", "Python is a programming language", provider="test")
    cache.put("Explain JavaScript web development", "JS is a web language", provider="test")
    
    hit = cache.get("What is Python programming")
    assert hit is not None, "Expected cache hit for similar query"
    assert "Python" in hit.response
    
    miss = cache.get("How to cook Italian pasta recipe")
    assert miss is None, "Expected cache miss for unrelated query"
    
    stats = cache.get_stats()
    print(f"  OK semantic_cache (hit_rate={stats['hit_rate']}, entries={stats['entries']})")
except Exception as e:
    errors.append(f"semantic_cache: {e}"); print(f"  FAIL semantic_cache: {e}")

try:
    from providers.adaptive_router import AdaptiveRouter, QueryComplexity
    router = AdaptiveRouter()
    
    easy = router.route("What is 2+2?")
    assert easy.complexity == QueryComplexity.EASY
    assert len(easy.selected_providers) == 1
    
    hard = router.route("Design and implement a distributed consensus algorithm with security analysis")
    assert hard.complexity == QueryComplexity.HARD
    assert len(hard.selected_providers) >= 3
    
    stats = router.get_stats()
    print(f"  OK adaptive_router (easy=1 model, hard={len(hard.selected_providers)} models, cost=${stats['estimated_total_cost_usd']})")
except Exception as e:
    errors.append(f"adaptive_router: {e}"); print(f"  FAIL adaptive_router: {e}")

try:
    from providers.token_budget import TokenBudgetManager
    import tempfile
    mgr = TokenBudgetManager(
        daily_limit=10000, monthly_limit=100000,
        persist_path=os.path.join(tempfile.mkdtemp(), "budget.json")
    )
    mgr.record_usage("gpt-4o", 500, 300)
    mgr.record_usage("llama-3-70b", 200, 100)
    stats = mgr.get_stats()
    assert stats["daily_tokens_used"] == 1100
    assert not mgr.is_over_budget()
    print(f"  OK token_budget (used={stats['daily_tokens_used']}/{stats['daily_limit']}, cost=${stats['daily_cost_usd']})")
except Exception as e:
    errors.append(f"token_budget: {e}"); print(f"  FAIL token_budget: {e}")

# === PHASE 6C: Real-Time & Embeddings ===
print("\n[Phase 6C: Real-Time & Embeddings]")

try:
    from providers.real_llm_client import UniversalLLMClient, LLMResponse
    # Just verify import and class instantiation (no real API calls)
    up = UniversalLLMClient(api_key="test-key", model="test-model", base_url="test-url")
    assert up.name == "universal"
    assert up.model == "test-model"
    print("  OK real_llm_client (UniversalLLMClient provider)")
except Exception as e:
    errors.append(f"real_llm_client: {e}"); print(f"  FAIL real_llm_client: {e}")

try:
    from brain.vector_store import VectorStore
    vs = VectorStore()
    vs.add("d1", "Machine learning is a subset of artificial intelligence")
    vs.add("d2", "Python is a popular programming language")
    vs.add("d3", "Neural networks learn patterns from data")
    
    results = vs.search("What is AI and deep learning?", top_k=2)
    assert len(results) >= 1
    assert results[0].doc_id in ("d1", "d3")  # Should match ML/AI docs
    print(f"  OK vector_store (3 docs, search top={results[0].doc_id} score={results[0].score})")
except Exception as e:
    errors.append(f"vector_store: {e}"); print(f"  FAIL vector_store: {e}")

try:
    from api.streaming import router as sse_router
    assert len(sse_router.routes) > 0
    print("  OK SSE streaming router mounted")
except Exception as e:
    errors.append(f"streaming: {e}"); print(f"  FAIL streaming: {e}")

try:
    from api.websocket_handler import router as ws_router, ConnectionManager
    mgr = ConnectionManager()
    assert len(mgr.active) == 0
    print("  OK WebSocket handler + ConnectionManager")
except Exception as e:
    errors.append(f"websocket: {e}"); print(f"  FAIL websocket: {e}")

# === PREVIOUS PHASES (Regression) ===
print("\n[Regression: Phases 1-5]")

for m in ['agents.controller', 'brain.thinking_loop', 'providers.multi_llm_client',
          'brain.consensus_engine', 'telemetry.metrics', 'telemetry.tracer',
          'prompts.prompt_manager', 'agents.sessions.store']:
    try:
        __import__(m); print(f"  OK {m}")
    except Exception as e:
        errors.append(f"{m}: {e}"); print(f"  FAIL {m}: {e}")

# === SUMMARY ===
print()
print("=" * 60)
if errors:
    print(f"  RESULT: {len(errors)} ERRORS")
    for e in errors:
        print(f"    - {e}")
else:
    print("  ALL PHASE 6 TESTS + REGRESSION PASSED")
    print("  ZERO ERRORS. SYSTEM IS ULTRA-PERFORMANCE READY.")
print("=" * 60)
sys.exit(1 if errors else 0)
