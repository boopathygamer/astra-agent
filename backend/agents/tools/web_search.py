"""
Deep & Dark Web Researcher Tool
───────────────────────────────
Empowers the Logic Engine to autonomously query the surface internet,
the deep web (academic databases like Arxiv), and the dark web (via Ahmia)
to extract highly precise data and prevent hallucinations.
"""

import logging
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import defusedxml.ElementTree as ET

from agents.tools.registry import registry, ToolRiskLevel

logger = logging.getLogger(__name__)

# ── HTTP session with connection pooling and retries ──
_http_session = requests.Session()
_retry_strategy = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
)
_adapter = HTTPAdapter(max_retries=_retry_strategy, pool_connections=5, pool_maxsize=10)
_http_session.mount("https://", _adapter)
_http_session.mount("http://", _adapter)
_http_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})
_DEFAULT_TIMEOUT = 10  # seconds

# Attempt to load DDGS
try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False
    logger.warning("duckduckgo-search not installed. Surface web search will fail.")

# Army Agent Defense Link
try:
    from agents.justice.army import army_command
except ImportError:
    army_command = None


def _scrape_clean_text(url: str, timeout: int = 10) -> str:
    """Helper to heavily scrape and strip a webpage down to pure text."""
    
    # 🛡️ Army Agent Network Inspection (Rule 4)
    if army_command and not army_command.inspect_network_payload(url):
         return "[NETWORK BLOCKED] The Army Agent has blocked this request due to malicious domain signatures."

    try:
        resp = _http_session.get(url, timeout=_DEFAULT_TIMEOUT)
        if resp.status_code != 200:
            return f"Error: Status {resp.status_code}"
            
        soup = BeautifulSoup(resp.text, "html.parser")
        for script in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            script.extract()
            
        text = soup.get_text(separator=' ')
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return clean_text[:5000] + "... [TRUNCATED]"
    except requests.Timeout:
        return "Error: Timeout waiting for page."
    except Exception as e:
        return f"Error scraping page: {str(e)}"


def _search_surface_web(query: str, max_results: int, deep_scrape: bool) -> List[Dict[str, str]]:
    """Standard DuckDuckGo Web Search."""
    if not HAS_DDGS:
        return [{"error": "duckduckgo-search missing"}]
        
    results = []
    try:
        with DDGS() as ddgs:
            search_results = list(ddgs.text(query, max_results=max_results))
            for res in search_results:
                item = {
                    "source": "Surface (DDG)",
                    "title": res.get("title", ""),
                    "href": res.get("href", ""),
                    "snippet": res.get("body", "")
                }
                if deep_scrape and item["href"]:
                    item["full_content"] = _scrape_clean_text(item["href"])
                results.append(item)
    except Exception as e:
        logger.error(f"Surface search failed: {e}")
        
    return results


def _search_deep_web(query: str, max_results: int) -> List[Dict[str, str]]:
    """Query ArXiv for physics, math, and computer science papers."""
    results = []
    try:
        url = f"http://export.arxiv.org/api/query?search_query=all:{query}&start=0&max_results={max_results}"
        resp = _http_session.get(url, timeout=_DEFAULT_TIMEOUT)
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
                title = entry.find("{http://www.w3.org/2005/Atom}title").text
                summary = entry.find("{http://www.w3.org/2005/Atom}summary").text
                link = entry.find("{http://www.w3.org/2005/Atom}id").text
                
                results.append({
                    "source": "Deep Web (ArXiv)",
                    "title": title.strip().replace('\n', ' '),
                    "href": link.strip(),
                    "snippet": summary.strip()[:1000] + "..." # Keep abstract
                })
    except Exception as e:
        logger.error(f"Deep web (ArXiv) search failed: {e}")
        
    return results


def _search_dark_web(query: str, max_results: int) -> List[Dict[str, str]]:
    """Scrape Ahmia.fi to find .onion dark web links."""
    results = []
    try:
        url = f"https://ahmia.fi/search/?q={query}"
        resp = _http_session.get(url, timeout=15)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            results_list = soup.find_all("li", class_="searchResultsItem")
            
            for item in results_list[:max_results]:
                title_tag = item.find("h4")
                cite_tag = item.find("cite")
                desc_tag = item.find("p")
                
                title = title_tag.text.strip() if title_tag else "Unknown"
                href = cite_tag.text.strip() if cite_tag else "Unknown .onion"
                snippet = desc_tag.text.strip() if desc_tag else "No description"
                
                # Note: We CANNOT deep scrape .onion links without a Tor proxy.
                # So we only return the Ahmia snippet.
                results.append({
                    "source": "Dark Web (Ahmia/Tor)",
                    "title": title,
                    "href": href,
                    "snippet": snippet
                })
    except Exception as e:
        logger.error(f"Dark web (Ahmia) search failed: {e}")
        
    return results


@registry.register(
    name="advanced_web_search",
    description="Search the internet, including social media, academic (Deep Web) and Tor (Dark Web) databases. Use 'network' parameter to select the appropriate scope.",
    risk_level=ToolRiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The exact search query to look up (e.g. 'latest James Webb telescope data' or 'quantum computing papers')."
            },
            "network": {
                "type": "string",
                "enum": ["surface", "deep", "dark", "social", "all"],
                "description": "Which network to search. 'surface' = normal news/data. 'deep' = Physics/Math/Academic papers on ArXiv. 'dark' = Tor .onion links via Ahmia. 'social' = Reddit/X/Forums. 'all' = search all networks.",
                "default": "surface"
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results to extract per network.",
                "default": 3
            },
            "deep_scrape": {
                "type": "boolean",
                "description": "If True, the tool will visit standard URLs and download the full text of the articles. (Does NOT work on 'dark' network).",
                "default": False
            }
        },
        "required": ["query"]
    }
)
def advanced_web_search(query: str, network: str = "surface", max_results: int = 3, deep_scrape: bool = False) -> Dict[str, Any]:
    """Execute a targeted recursive web search across designated networks."""
    
    logger.info(f"🌐 Initiating Web Search: '{query}' [Network: {network} | Deep Scrape: {deep_scrape}]")
    
    aggregated_results = []
    
    # helper for social simulation
    def _search_social(q, max_res):
        try:
            with DDGS() as ddgs:
                # Add site-specific constraints for Reddit and X/Twitter
                res_reddit = list(ddgs.text(f"site:reddit.com {q}", max_results=max_res//2 + 1))
                res_x = list(ddgs.text(f"site:twitter.com OR site:x.com {q}", max_results=max_res//2 + 1))
                
                social_res = []
                for r in res_reddit + res_x:
                    social_res.append({
                        "source": "Social Media (Reddit/X)",
                        "title": r.get("title", ""),
                        "href": r.get("href", ""),
                        "snippet": r.get("body", "")
                    })
                return social_res[:max_res]
        except Exception as e:
            logger.error(f"Social search failed: {e}")
            return []

    # 1. Surface Web
    if network in ["surface", "all"]:
        aggregated_results.extend(_search_surface_web(query, max_results, deep_scrape))
        
    # 2. Deep Web
    if network in ["deep", "all"]:
        # Deep scrape is not needed for ArXiv as the abstract is usually sufficient
        aggregated_results.extend(_search_deep_web(query, max_results))
        
    # 3. Dark Web
    if network in ["dark", "all"]:
        aggregated_results.extend(_search_dark_web(query, max_results))
        
    # 4. Social Media
    if network in ["social", "all"]:
        aggregated_results.extend(_search_social(query, max_results))
        
    logger.info(f"🌐 Successfully retrieved {len(aggregated_results)} total results.")
    
    return {
        "query": query,
        "network_requested": network,
        "results": aggregated_results
    }
