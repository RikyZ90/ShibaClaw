import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from shibaclaw.agent.knowledge_manager import KnowledgeManager, RAG_AVAILABLE

class FakeEmbeddings:
    def embed_documents(self, texts):
        return [[0.1, 0.2] for _ in texts]
    def embed_query(self, text):
        return [0.1, 0.2]

@pytest.fixture
def workspace_dir(tmp_path):
    mem_dir = tmp_path / "memory" / "knowledge"
    mem_dir.mkdir(parents=True)
    return tmp_path

@pytest.fixture
def km(workspace_dir):
    return KnowledgeManager(workspace_dir)

def test_sanitize_id_valid(km):
    assert km._sanitize_id("valid-id_123") == "valid-id_123"

def test_sanitize_id_invalid(km):
    with pytest.raises(ValueError, match="Invalid collection ID format"):
        km._sanitize_id("../invalid")

@pytest.mark.skipif(not RAG_AVAILABLE, reason="RAG dependencies are not installed")
@patch("shibaclaw.agent.knowledge_manager.KnowledgeManager.embeddings", new_callable=PropertyMock, return_value=FakeEmbeddings())
def test_path_traversal_filename(mock_embeddings, km, tmp_path):
    km.create_collection("test", "test col")
    
    # Create a dummy file to upload
    dummy_file = tmp_path / "dummy.txt"
    dummy_file.write_text("hello")
    
    # Attempt path traversal via filename
    km.add_document("test", dummy_file, "../../../hacked.txt")
    
    # Verify the file was saved with just the basename
    coll_dir = km._get_collection_dir("test")
    docs_dir = coll_dir / "docs"
    
    assert (docs_dir / "hacked.txt").exists()

@pytest.mark.skipif(not RAG_AVAILABLE, reason="RAG dependencies are not installed")
@patch('shibaclaw.agent.knowledge_manager.KnowledgeManager._get_loader')
@patch("shibaclaw.agent.knowledge_manager.KnowledgeManager.embeddings", new_callable=PropertyMock, return_value=FakeEmbeddings())
def test_atomicity_on_parsing_error(mock_embeddings, mock_get_loader, km, tmp_path):
    km.create_collection("test", "test col")
    
    # Mock loader to throw an exception
    mock_loader = MagicMock()
    mock_loader.load.side_effect = Exception("Parsing failed")
    mock_get_loader.return_value = mock_loader
    
    dummy_file = tmp_path / "dummy.txt"
    dummy_file.write_text("hello")
    
    with pytest.raises(Exception, match="Parsing failed"):
        km.add_document("test", dummy_file, "dummy.txt")
        
    # Verify the copied file was cleaned up
    coll_dir = km._get_collection_dir("test")
    assert not (coll_dir / "docs" / "dummy.txt").exists()

@pytest.mark.skipif(not RAG_AVAILABLE, reason="RAG dependencies are not installed")
@patch("shibaclaw.agent.knowledge_manager.KnowledgeManager.embeddings", new_callable=PropertyMock, return_value=FakeEmbeddings())
def test_faiss_caching(mock_embeddings, km, tmp_path):
    km.create_collection("test", "test col")
    dummy_file = tmp_path / "dummy.txt"
    dummy_file.write_text("hello")
    km.add_document("test", dummy_file, "dummy.txt")
    
    assert "test" in km._faiss_cache
    
    # Delete collection should clear cache
    km.delete_collection("test")
    assert "test" not in km._faiss_cache


@patch("shibaclaw.config.loader.load_config")
def test_embeddings_provider_resolution(mock_load_config, km):
    mock_cfg = MagicMock()
    mock_cfg.rag.provider = "gemini"
    mock_cfg.rag.resolve_api_key.return_value = None
    mock_cfg.rag.api_base = ""
    mock_cfg.rag.model = ""
    
    mock_gemini_prov = MagicMock()
    mock_gemini_prov.resolve_api_key.return_value = "fake-gemini-key"
    mock_cfg.providers.gemini = mock_gemini_prov
    mock_load_config.return_value = mock_cfg
    
    with patch("shibaclaw.agent.knowledge_manager._get_embeddings") as mock_get:
        _ = km.embeddings
        mock_gemini_prov.resolve_api_key.assert_called_once_with("gemini")
        mock_get.assert_called_once_with("gemini", "fake-gemini-key", "", "")

