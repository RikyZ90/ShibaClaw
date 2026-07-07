"""Knowledge Search tool."""

from typing import Any, List

from shibaclaw.agent.tools.base import Tool
from shibaclaw.agent.knowledge_manager import KnowledgeManager
from shibaclaw.webui.agent_manager import agent_manager

class KnowledgeSearchTool(Tool):
    @property
    def name(self) -> str:
        return "knowledge_search"

    @property
    def description(self) -> str:
        return "Search for information inside user-created Knowledge Bases (Collezioni) via semantic similarity."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "collection_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "The IDs of the Knowledge Bases to search in. Look at your system prompt to see which ones are available.",
                },
                "query": {
                    "type": "string",
                    "description": "The question or concept to search for.",
                }
            },
            "required": ["collection_ids", "query"],
        }

    async def execute(self, **kwargs: Any) -> str:
        query = kwargs.get("query")
        collection_ids = kwargs.get("collection_ids")
        
        if not query or not collection_ids:
            return "Error: query and collection_ids are required."
            
        try:
            if not agent_manager.config:
                agent_manager.load_latest_config()
                
            km = KnowledgeManager(agent_manager.config.workspace_path)
            docs = km.search(collection_ids, query, k=5)
            
            if not docs:
                return "No relevant information found in the specified Knowledge Bases."
                
            out = ["### Knowledge Search Results ###"]
            for i, doc in enumerate(docs):
                out.append(f"--- Document {i+1} (Source: {doc.metadata.get('source', 'Unknown')}, Score: {doc.metadata.get('score', 0):.3f}) ---")
                out.append(doc.page_content)
                
            return "\n".join(out)
            
        except Exception as e:
            return f"Error executing knowledge search: {e}"
