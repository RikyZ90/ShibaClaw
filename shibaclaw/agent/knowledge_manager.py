import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_community.document_loaders import (
    BSHTMLLoader,
    CSVLoader,
    PyPDFLoader,
    TextLoader,
)
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

class KnowledgeManager:
    """Manages cross-session Knowledge Bases using FAISS and LangChain."""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.base_dir = self.workspace_path / "memory" / "knowledge"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # Using a reliable default local model for embeddings
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    def _get_collection_dir(self, collection_id: str) -> Path:
        return self.base_dir / collection_id

    def list_collections(self) -> List[Dict[str, Any]]:
        collections = []
        for path in self.base_dir.iterdir():
            if path.is_dir():
                meta_file = path / "meta.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                            collections.append(meta)
                    except Exception as e:
                        logger.error(f"Error reading meta for {path.name}: {e}")
        return collections

    def create_collection(self, collection_id: str, name: str, description: str = "") -> Dict[str, Any]:
        coll_dir = self._get_collection_dir(collection_id)
        if coll_dir.exists():
            raise ValueError(f"Collection {collection_id} already exists")
        coll_dir.mkdir(parents=True)
        meta = {"id": collection_id, "name": name, "description": description, "files": []}
        with open(coll_dir / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        return meta

    def delete_collection(self, collection_id: str):
        coll_dir = self._get_collection_dir(collection_id)
        if coll_dir.exists():
            shutil.rmtree(coll_dir)

    def _get_loader(self, file_path: Path):
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            return PyPDFLoader(str(file_path))
        elif ext == ".csv":
            return CSVLoader(str(file_path))
        elif ext in [".html", ".htm"]:
            return BSHTMLLoader(str(file_path))
        else:
            return TextLoader(str(file_path))

    def add_document(self, collection_id: str, file_path: Path, filename: str) -> None:
        coll_dir = self._get_collection_dir(collection_id)
        if not coll_dir.exists():
            raise ValueError(f"Collection {collection_id} does not exist")
            
        # Copy file to collection
        docs_dir = coll_dir / "docs"
        docs_dir.mkdir(exist_ok=True)
        dest_path = docs_dir / filename
        shutil.copy2(file_path, dest_path)
        
        # Load and split
        loader = self._get_loader(dest_path)
        documents = loader.load()
        chunks = self.text_splitter.split_documents(documents)
        
        # Update FAISS
        faiss_dir = coll_dir / "index"
        if faiss_dir.exists():
            vectorstore = FAISS.load_local(str(faiss_dir), self.embeddings, allow_dangerous_deserialization=True)
            vectorstore.add_documents(chunks)
        else:
            vectorstore = FAISS.from_documents(chunks, self.embeddings)
            
        vectorstore.save_local(str(faiss_dir))
        
        # Update meta
        meta_file = coll_dir / "meta.json"
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        if filename not in meta.get("files", []):
            meta.setdefault("files", []).append(filename)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    def search(self, collection_ids: List[str], query: str, k: int = 4) -> List[Any]:
        results = []
        for cid in collection_ids:
            faiss_dir = self._get_collection_dir(cid) / "index"
            if faiss_dir.exists():
                try:
                    vectorstore = FAISS.load_local(str(faiss_dir), self.embeddings, allow_dangerous_deserialization=True)
                    # Use similarity search with score to potentially sort them later
                    docs = vectorstore.similarity_search_with_score(query, k=k)
                    for doc, score in docs:
                        doc.metadata["collection_id"] = cid
                        doc.metadata["score"] = float(score)
                        results.append((score, doc))
                except Exception as e:
                    logger.error(f"Error searching collection {cid}: {e}")
                    
        # Sort by distance (lower is closer)
        results.sort(key=lambda x: x[0])
        # Return top k overall
        return [doc for score, doc in results[:k]]
