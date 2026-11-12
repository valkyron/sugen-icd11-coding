"""Unit tests for ICD-11 coding pipeline."""

import os
from unittest.mock import MagicMock, patch
import pytest

from coder.budget import BudgetTracker
from coder.postprocess import clean_predictions, norm_code
from coder.retrieve import retrieve_candidates
from coder.extract import extract_diagnostic_query
from coder.local_ranker import rank_local_candidates
from coder.llm_reranker import rerank_with_llm


def test_norm_code():
    assert norm_code("1F40.Z") == "1F40.Z"
    assert norm_code("NC72.2&XK8G") == "NC72.2"
    assert norm_code("CA40.0/XK9A") == "CA40.0"
    assert norm_code(None) is None


def test_clean_predictions():
    # 1A00 is valid (Cholera), INVALID999 is not
    raw = ["1A00", "INVALID999", "1A07.Z", "1A00", "1F40.Z", "CA40.Z"]
    cleaned = clean_predictions(raw, max_codes=3)
    assert len(cleaned) <= 3
    assert "INVALID999" not in cleaned
    assert cleaned[0] == "1A00"
    assert cleaned[1] == "1A07.Z"
    # Deduplication
    assert cleaned.count("1A00") == 1


def test_budget_tracker_hard_stop():
    tracker = BudgetTracker(max_budget_usd=0.01)
    assert tracker.can_call() is True

    # Record 100k tokens
    tracker.record_usage(prompt_tokens=50000, completion_tokens=10000)
    summary = tracker.summary()
    assert summary["calls"] == 1
    assert summary["cost_usd"] > 0

    # Exhaust budget
    tracker.record_usage(prompt_tokens=50000, completion_tokens=50000)
    assert tracker.can_call() is False


def test_retrieval_returns_valid_candidates():
    query = "malaria fever with chills and rigors falciparum"
    candidates = retrieve_candidates(query, top_k=10)
    assert len(candidates) == 10
    codes = [c["code"] for c in candidates]
    # Falciparum malaria should be in top candidates
    assert any("1F40" in c for c in codes)


def test_local_ranker_favors_leaf_nodes():
    dummy_cands = [
        {"code": "1A07", "title": "Typhoid fever", "leaf": False, "residual": False, "depth": 1, "bm25_score": 10.0},
        {"code": "1A07.Z", "title": "Typhoid fever, unspecified", "leaf": True, "residual": True, "depth": 2, "bm25_score": 9.5},
    ]
    ranked = rank_local_candidates(dummy_cands)
    assert len(ranked) >= 1
    # Leaf .Z should be promoted above parent
    assert ranked[0] == "1A07.Z"


def test_llm_reranker_mock():
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"codes": ["1A07.Z", "1A07.0"]}'
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_resp.usage.prompt_tokens = 150
    mock_resp.usage.completion_tokens = 15
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("coder.llm_reranker.get_llm_client", return_value=("openai", mock_client, "gpt-4o-mini")):
        cands = [
            {"code": "1A07.Z", "title": "Typhoid fever, unspecified", "leaf": True, "residual": True, "depth": 2, "bm25_score": 10.0},
            {"code": "1A07.0", "title": "Typhoid fever with heart complications", "leaf": True, "residual": False, "depth": 2, "bm25_score": 8.0},
        ]
        result = rerank_with_llm("test-01", "Typhoid culture confirmed", cands)
        assert result == ["1A07.Z", "1A07.0"]
        assert mock_client.chat.completions.create.called
