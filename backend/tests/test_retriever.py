"""
Tests for the three-stage hybrid retrieval pipeline.
Qdrant and embedder are mocked — tests verify pipeline logic, not model accuracy.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestHybridSearch:

    @pytest.mark.asyncio
    async def test_colbert_results_returned_on_success(self):
        """When ColBERT search succeeds, results are returned with retrieval tag."""
        from app.services.retriever import hybrid_search

        fake_point = MagicMock()
        fake_point.score = 0.92
        fake_point.payload = {
            "fact_id":   "fact-1",
            "statement": "Revenue was $100M",
            "subject":   "Acme Corp",
            "doc_id":    "doc-1",
            "confidence": 0.9,
        }

        mock_result = MagicMock()
        mock_result.points = [fake_point]

        mock_qdrant = AsyncMock()
        mock_qdrant.query_points = AsyncMock(return_value=mock_result)

        fake_emb = {
            "dense":          [0.1] * 1024,
            "sparse_indices": [1, 2, 3],
            "sparse_values":  [0.5, 0.3, 0.2],
            "colbert":        [[0.1] * 128, [0.2] * 128],
        }

        with patch("app.services.retriever.get_qdrant", return_value=mock_qdrant), \
             patch("app.services.retriever.embed_query", side_effect=lambda q: fake_emb):
            results = await hybrid_search("revenue growth", limit=5)

        assert len(results) == 1
        assert results[0]["fact_id"] == "fact-1"
        assert results[0]["score"] == pytest.approx(0.92)
        assert results[0]["retrieval"] == "colbert_hybrid"

    @pytest.mark.asyncio
    async def test_fallback_to_dense_when_colbert_empty(self):
        """When ColBERT returns zero results, falls back to dense search."""
        from app.services.retriever import hybrid_search

        fake_point = MagicMock()
        fake_point.score = 0.78
        fake_point.payload = {
            "fact_id":   "fact-2",
            "statement": "GDP grew 6.4%",
            "subject":   "India",
            "doc_id":    "doc-2",
            "confidence": 0.85,
        }

        mock_qdrant = AsyncMock()
        # ColBERT query returns empty
        empty_result = MagicMock()
        empty_result.points = []
        mock_qdrant.query_points = AsyncMock(return_value=empty_result)
        # Dense search returns one result
        mock_qdrant.search = AsyncMock(return_value=[fake_point])

        fake_emb = {
            "dense":          [0.1] * 1024,
            "sparse_indices": [1, 2],
            "sparse_values":  [0.5, 0.5],
            "colbert":        [[0.1] * 128],
        }

        with patch("app.services.retriever.get_qdrant", return_value=mock_qdrant), \
             patch("app.services.retriever.embed_query", side_effect=lambda q: fake_emb):
            results = await hybrid_search("GDP India", limit=5)

        assert len(results) == 1
        assert results[0]["fact_id"] == "fact-2"
        mock_qdrant.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_dense_on_colbert_exception(self):
        """When ColBERT raises an error (e.g. no points have colbert vectors), dense is used."""
        from app.services.retriever import hybrid_search

        fake_point = MagicMock()
        fake_point.score = 0.80
        fake_point.payload = {
            "fact_id":   "fact-3",
            "statement": "Net profit was €50M",
            "subject":   "BASF SE",
            "doc_id":    "doc-3",
            "confidence": 0.88,
        }

        mock_qdrant = AsyncMock()
        mock_qdrant.query_points = AsyncMock(side_effect=RuntimeError("no colbert vectors"))
        mock_qdrant.search = AsyncMock(return_value=[fake_point])

        fake_emb = {
            "dense":          [0.1] * 1024,
            "sparse_indices": [5, 6],
            "sparse_values":  [0.4, 0.6],
            "colbert":        [[0.2] * 128],
        }

        with patch("app.services.retriever.get_qdrant", return_value=mock_qdrant), \
             patch("app.services.retriever.embed_query", side_effect=lambda q: fake_emb):
            results = await hybrid_search("profit", limit=5)

        assert len(results) == 1
        assert results[0]["fact_id"] == "fact-3"

    @pytest.mark.asyncio
    async def test_doc_id_filter_passed_to_qdrant(self):
        """When doc_id is supplied, filter is included in the Qdrant call."""
        from app.services.retriever import hybrid_search

        mock_qdrant = AsyncMock()
        empty_result = MagicMock()
        empty_result.points = []
        mock_qdrant.query_points = AsyncMock(return_value=empty_result)
        mock_qdrant.search = AsyncMock(return_value=[])

        fake_emb = {
            "dense":          [0.0] * 1024,
            "sparse_indices": [],
            "sparse_values":  [],
            "colbert":        [[0.0] * 128],
        }

        with patch("app.services.retriever.get_qdrant", return_value=mock_qdrant), \
             patch("app.services.retriever.embed_query", side_effect=lambda q: fake_emb):
            await hybrid_search("test query", doc_id="specific-doc-id", limit=5)

        # query_points must have been called with a filter
        call_kwargs = mock_qdrant.query_points.call_args.kwargs
        assert call_kwargs.get("query_filter") is not None

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty_list(self):
        """No results from either stage → empty list returned, no exception."""
        from app.services.retriever import hybrid_search

        mock_qdrant = AsyncMock()
        empty = MagicMock()
        empty.points = []
        mock_qdrant.query_points = AsyncMock(return_value=empty)
        mock_qdrant.search = AsyncMock(return_value=[])

        fake_emb = {
            "dense":          [0.0] * 1024,
            "sparse_indices": [],
            "sparse_values":  [],
            "colbert":        [[0.0] * 128],
        }

        with patch("app.services.retriever.get_qdrant", return_value=mock_qdrant), \
             patch("app.services.retriever.embed_query", side_effect=lambda q: fake_emb):
            results = await hybrid_search("something obscure", limit=5)

        assert results == []


class TestEmbedColbert:

    def test_embed_colbert_returns_token_matrices(self):
        """embed_colbert should return one token matrix per input text."""
        import numpy as np
        from unittest.mock import patch, MagicMock

        fake_mat = np.random.randn(7, 128).astype(np.float32)
        mock_model = MagicMock()
        mock_model.embed.return_value = [fake_mat]

        with patch("app.services.embedder._colbert_model", mock_model), \
             patch("app.services.embedder._load_colbert", return_value=None):
            from app.services.embedder import embed_colbert
            result = embed_colbert(["Revenue was $100M"])

        assert len(result) == 1
        assert len(result[0]) == 7       # 7 tokens
        assert len(result[0][0]) == 128  # 128-dim per token

    def test_embed_colbert_multiple_texts(self):
        """One token matrix returned per input text."""
        import numpy as np
        from unittest.mock import patch, MagicMock

        fake_mats = [
            np.random.randn(6, 128).astype(np.float32),
            np.random.randn(10, 128).astype(np.float32),
        ]
        mock_model = MagicMock()
        mock_model.embed.return_value = fake_mats

        with patch("app.services.embedder._colbert_model", mock_model), \
             patch("app.services.embedder._load_colbert", return_value=None):
            from app.services.embedder import embed_colbert
            result = embed_colbert(["text one", "text two"])

        assert len(result) == 2
        assert len(result[0]) == 6
        assert len(result[1]) == 10
