import json
import logging
import os
import shutil
import re
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from filelock import FileLock

# Suppress Hugging Face Hub unauthenticated request warnings and disable progress bars
warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub")
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["HUGGINGFACE_HUB_VERBOSITY"] = "error"

try:
    from langchain_core.documents import Document  # noqa: E402
    from langchain_community.document_loaders import (  # noqa: E402
        BSHTMLLoader,
        CSVLoader,
        PyPDFLoader,
        TextLoader,
    )
    from langchain_community.vectorstores import FAISS  # noqa: E402
    from langchain_huggingface import HuggingFaceEmbeddings  # noqa: E402
    from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402
    RAG_AVAILABLE = True
except ImportError:
    class Document:
        pass
    RAG_AVAILABLE = False

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def _get_embeddings():
    if not RAG_AVAILABLE:
        raise RuntimeError("RAG dependencies are not installed. Please run `pip install 'shibaclaw[rag]'`.")
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

class KnowledgeManager:
    """Manages cross-session Knowledge Bases using FAISS and LangChain."""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.base_dir = self.workspace_path / "memory" / "knowledge"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if RAG_AVAILABLE:
            self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        else:
            self.text_splitter = None
        self._faiss_cache = {}
        
    @property
    def embeddings(self):
        # Lazy load embeddings to avoid blocking event loop on init
        return _get_embeddings()

    def _sanitize_id(self, collection_id: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]+$", collection_id):
            raise ValueError("Invalid collection ID format")
        return collection_id

    def _get_collection_dir(self, collection_id: str) -> Path:
        cid = self._sanitize_id(collection_id)
        return self.base_dir / cid

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
        meta_file = coll_dir / "meta.json"
        lock = FileLock(f"{meta_file}.lock")
        with lock:
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        return meta

    def update_collection(self, collection_id: str, name: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
        coll_dir = self._get_collection_dir(collection_id)
        if not coll_dir.exists():
            raise ValueError(f"Collection {collection_id} does not exist")
        meta_file = coll_dir / "meta.json"
        lock = FileLock(f"{meta_file}.lock")
        with lock:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if name is not None:
                meta["name"] = name
            if description is not None:
                meta["description"] = description
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        return meta

    def delete_collection(self, collection_id: str):
        coll_dir = self._get_collection_dir(collection_id)
        if coll_dir.exists():
            shutil.rmtree(coll_dir, ignore_errors=True)
        cid = self._sanitize_id(collection_id)
        if cid in self._faiss_cache:
            del self._faiss_cache[cid]

    def _get_loader(self, file_path: Path):
        if not RAG_AVAILABLE:
            raise RuntimeError("Local RAG dependencies are not installed. Please run `pip install 'shibaclaw[rag]'`.")
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            return PyPDFLoader(str(file_path))
        elif ext == ".csv":
            return CSVLoader(str(file_path))
        elif ext in [".html", ".htm"]:
            return BSHTMLLoader(str(file_path))
        else:
            return TextLoader(str(file_path), autodetect_encoding=True)

    def add_document(self, collection_id: str, file_path: Path, filename: str) -> None:
        if not RAG_AVAILABLE:
            raise RuntimeError("Local RAG dependencies are not installed. Please run `pip install 'shibaclaw[rag]'`.")
        coll_dir = self._get_collection_dir(collection_id)
        if not coll_dir.exists():
            raise ValueError(f"Collection {collection_id} does not exist")
            
        # Copy file to collection
        docs_dir = coll_dir / "docs"
        docs_dir.mkdir(exist_ok=True)
        safe_filename = Path(filename).name
        dest_path = docs_dir / safe_filename
        shutil.copy2(file_path, dest_path)
        
        try:
            # Load and split
            loader = self._get_loader(dest_path)
            documents = loader.load()
            chunks = self.text_splitter.split_documents(documents)
            
            # Update FAISS
            faiss_dir = coll_dir / "index"
            temp_faiss_dir = coll_dir / "index_tmp"
            
            if faiss_dir.exists():
                vectorstore = FAISS.load_local(str(faiss_dir), self.embeddings, allow_dangerous_deserialization=True)
                vectorstore.add_documents(chunks)
            else:
                vectorstore = FAISS.from_documents(chunks, self.embeddings)
                
            # Save to temporary directory first for atomic update
            vectorstore.save_local(str(temp_faiss_dir))
            
            # Atomic rename (replace existing)
            if faiss_dir.exists():
                shutil.rmtree(faiss_dir, ignore_errors=True)
            temp_faiss_dir.rename(faiss_dir)
            
            # Update cache
            cid = self._sanitize_id(collection_id)
            self._faiss_cache[cid] = vectorstore
            
            # Update meta safely
            meta_file = coll_dir / "meta.json"
            lock = FileLock(f"{meta_file}.lock")
            with lock:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                
                if "files" not in meta:
                    meta["files"] = []
                    
                if safe_filename not in meta["files"]:
                    meta["files"].append(safe_filename)
                    
                with open(meta_file, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)
                    
        except Exception as e:
            if dest_path.exists():
                os.remove(dest_path)
            if 'temp_faiss_dir' in locals() and temp_faiss_dir.exists():
                shutil.rmtree(temp_faiss_dir, ignore_errors=True)
            raise e

    def search(self, collection_ids: List[str], query: str, k: int = 4) -> List[Document]:
        if not RAG_AVAILABLE:
            raise RuntimeError("Local RAG dependencies are not installed. Please run `pip install 'shibaclaw[rag]'`.")
        results = []
        for cid in collection_ids:
            try:
                cid = self._sanitize_id(cid)
            except ValueError:
                continue

            if cid in self._faiss_cache:
                vectorstore = self._faiss_cache[cid]
            else:
                faiss_dir = self._get_collection_dir(cid) / "index"
                if faiss_dir.exists():
                    try:
                        vectorstore = FAISS.load_local(str(faiss_dir), self.embeddings, allow_dangerous_deserialization=True)
                        self._faiss_cache[cid] = vectorstore
                    except Exception as e:
                        logger.error(f"Error loading collection {cid}: {e}")
                        continue
                else:
                    continue

            try:
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
