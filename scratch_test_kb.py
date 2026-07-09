import sys
from pathlib import Path

# Add shibaclaw to path
sys.path.append(r"c:\Users\Rikyz\.gemini\antigravity\scratch\ShibaClaw")

from shibaclaw.agent.knowledge_manager import KnowledgeManager

wp = Path(r"c:\Users\Rikyz\.shibaclaw\workspace")
km = KnowledgeManager(wp)
docs = km.search(["revolut"], "revolut")
print(f"Found {len(docs)} docs")
if docs:
    for doc in docs:
        print(doc.page_content[:100])
