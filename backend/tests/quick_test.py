import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import logging; logging.disable(logging.CRITICAL)
errs = []

# 6A
try:
    from config.settings import ssl_config, token_budget_config
    print("OK settings")
except Exception as e: errs.append(str(e)); print("FAIL settings:", e)

try:
    from telemetry.log_exporter import StructuredLogExporter
    print("OK log_exporter")
except Exception as e: errs.append(str(e)); print("FAIL log_exporter:", e)

# 6B
try:
    from brain.semantic_cache import SemanticCache
    c = SemanticCache(similarity_threshold=0.3)
    c.put("What is Python programming language", "Python is a language")
    h = c.get("What is Python programming")
    print("OK semantic_cache hit=", h is not None)
except Exception as e: errs.append(str(e)); print("FAIL cache:", e)

try:
    from providers.adaptive_router import AdaptiveRouter, QueryComplexity
    r = AdaptiveRouter()
    e = r.route("Hi")
    h = r.route("Design and implement a distributed consensus algorithm with security analysis")
    print("OK adaptive_router easy=", e.complexity.value, "hard=", h.complexity.value)
except Exception as e: errs.append(str(e)); print("FAIL router:", e)

try:
    import tempfile
    from providers.token_budget import TokenBudgetManager
    m = TokenBudgetManager(daily_limit=10000, persist_path=os.path.join(tempfile.mkdtemp(), "b.json"))
    m.record_usage("gpt-4o", 500, 300)
    s = m.get_stats()
    print("OK token_budget used=", s["daily_tokens_used"])
except Exception as e: errs.append(str(e)); print("FAIL budget:", e)

# 6C
try:
    from providers.real_llm_client import OpenAIProvider, ClaudeProvider, GeminiProvider
    print("OK real_llm_client")
except Exception as e: errs.append(str(e)); print("FAIL llm:", e)

try:
    from brain.vector_store import VectorStore
    v = VectorStore()
    v.add("d1", "Machine learning artificial intelligence")
    v.add("d2", "Python programming language")
    r = v.search("AI machine learning", top_k=1)
    print("OK vector_store top=", r[0].doc_id, "score=", r[0].score)
except Exception as e: errs.append(str(e)); print("FAIL vector:", e)

try:
    from api.streaming import router as sr
    print("OK sse_streaming routes=", len(sr.routes))
except Exception as e: errs.append(str(e)); print("FAIL sse:", e)

try:
    from api.websocket_handler import router as wr
    print("OK websocket routes=", len(wr.routes))
except Exception as e: errs.append(str(e)); print("FAIL ws:", e)

# Regression
for mod in ["agents.controller", "brain.thinking_loop", "brain.consensus_engine", "prompts.prompt_manager"]:
    try:
        __import__(mod)
        print("OK", mod)
    except Exception as e:
        errs.append(str(e))
        print("FAIL", mod, ":", e)

print()
if errs:
    print("ERRORS:", len(errs))
    for e in errs:
        print(" -", e)
else:
    print("ALL PASSED. ZERO ERRORS.")
