"""
Unit tests for embedding and generator inference code.
All external I/O (HTTP, HF client, Anthropic client) is mocked — no live APIs needed.
"""
import pytest
from unittest.mock import MagicMock, patch

from src.inference.embedding import HuggingFaceEmbeddingService
from src.inference.generator import LLMResponseGenerator, PromptBuilder
from src.inference.adapters.huggingface import HuggingFaceAdapter
from src.inference.adapters.claude import ClaudeAdapter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CHUNKS = [
    {"filename": "doc.pdf", "page": 1, "content": "The sky is blue."},
    {"filename": "doc.pdf", "page": 2, "content": "Water is wet."},
]

SAMPLE_HISTORY = [
    {"role": "user",      "content": "What color is the sky?"},
    {"role": "assistant", "content": "Blue."},
]


# ===========================================================================
# HuggingFaceEmbeddingService
# ===========================================================================

class TestHuggingFaceEmbeddingService:

    def test_empty_input_returns_empty_list(self):
        svc = HuggingFaceEmbeddingService()
        assert svc.embed([]) == []

    def test_raises_when_token_missing(self):
        svc = HuggingFaceEmbeddingService()
        with patch("src.inference.embedding.settings") as mock_settings:
            mock_settings.hf_token = ""
            with pytest.raises(RuntimeError, match="HF_TOKEN"):
                svc.embed(["hello"])

    def test_single_batch_calls_fetch_once(self):
        svc = HuggingFaceEmbeddingService()
        fake_vectors = [[0.1] * 384, [0.2] * 384]
        with patch.object(svc, "_fetch_embeddings", return_value=fake_vectors) as mock_fetch:
            with patch("src.inference.embedding.settings") as mock_settings:
                mock_settings.hf_token = "tok"
                mock_settings.hf_embed_batch_size = 32
                result = svc.embed(["text a", "text b"])
        mock_fetch.assert_called_once_with(["text a", "text b"])
        assert result == fake_vectors

    def test_large_input_batches_correctly(self):
        svc = HuggingFaceEmbeddingService()
        texts = [f"text {i}" for i in range(5)]
        batch_vectors = [[float(i)] * 384 for i in range(5)]

        def fake_fetch(batch):
            start = int(batch[0].split()[-1])
            return [batch_vectors[start + j] for j in range(len(batch))]

        with patch.object(svc, "_fetch_embeddings", side_effect=fake_fetch):
            with patch("src.inference.embedding.settings") as mock_settings:
                mock_settings.hf_token = "tok"
                mock_settings.hf_embed_batch_size = 2
                result = svc.embed(texts, batch_size=2)

        assert len(result) == 5
        assert result[0] == batch_vectors[0]
        assert result[4] == batch_vectors[4]

    def test_fetch_normalises_single_vector_response(self):
        """HF API sometimes returns a flat list for a single input; must be wrapped."""
        svc = HuggingFaceEmbeddingService()
        flat_vector = [0.1] * 384
        mock_response = MagicMock()
        mock_response.json.return_value = flat_vector  # flat, not nested
        mock_response.raise_for_status = MagicMock()

        with patch("src.inference.embedding.httpx.post", return_value=mock_response):
            result = svc._fetch_embeddings(["single text"])

        assert result == [flat_vector]

    def test_fetch_raises_on_http_error(self):
        import httpx
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=MagicMock()
        )
        svc = HuggingFaceEmbeddingService()
        with patch("src.inference.embedding.httpx.post", return_value=mock_response):
            with pytest.raises(Exception):
                svc._fetch_embeddings(["text"])


# ===========================================================================
# PromptBuilder
# ===========================================================================

class TestPromptBuilder:

    def test_format_chunks_produces_numbered_blocks(self):
        text = PromptBuilder.format_chunks(SAMPLE_CHUNKS)
        assert "[1] [doc.pdf p.1]" in text
        assert "[2] [doc.pdf p.2]" in text
        assert "The sky is blue." in text
        assert "Water is wet." in text

    def test_format_chunks_handles_missing_fields(self):
        chunks = [{"content": "bare content"}]
        text = PromptBuilder.format_chunks(chunks)
        assert "[1] [unknown p.?]" in text
        assert "bare content" in text

    def test_format_chunks_strips_whitespace(self):
        chunks = [{"filename": "f.pdf", "page": 1, "content": "  padded  "}]
        text = PromptBuilder.format_chunks(chunks)
        assert "padded" in text
        assert "  padded  " not in text

    def test_build_messages_structure(self):
        messages = PromptBuilder.build_messages("What color?", SAMPLE_CHUNKS, [])
        roles = [m["role"] for m in messages]
        assert roles[0] == "system"
        assert roles[-1] == "user"

    def test_build_messages_includes_system_prompt(self):
        messages = PromptBuilder.build_messages("q", SAMPLE_CHUNKS, [])
        assert messages[0]["content"] == PromptBuilder.SYSTEM_PROMPT

    def test_build_messages_embeds_context_in_user_turn(self):
        messages = PromptBuilder.build_messages("What color?", SAMPLE_CHUNKS, [])
        user_content = messages[-1]["content"]
        assert "The sky is blue." in user_content
        assert "What color?" in user_content

    def test_build_messages_includes_history(self):
        messages = PromptBuilder.build_messages("follow-up", SAMPLE_CHUNKS, SAMPLE_HISTORY)
        roles = [m["role"] for m in messages]
        # system, user(history), assistant(history), user(question)
        assert roles.count("user") == 2
        assert roles.count("assistant") == 1

    def test_build_messages_caps_history_at_6(self):
        long_history = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
        messages = PromptBuilder.build_messages("q", SAMPLE_CHUNKS, long_history)
        # system + 6 history + 1 user question = 8
        assert len(messages) == 8

    def test_build_messages_no_history(self):
        messages = PromptBuilder.build_messages("q", SAMPLE_CHUNKS, [])
        # system + user question only
        assert len(messages) == 2


# ===========================================================================
# HuggingFaceAdapter
# ===========================================================================

class TestHuggingFaceAdapter:

    def _make_adapter(self):
        with patch("src.inference.adapters.huggingface.InferenceClient"):
            adapter = HuggingFaceAdapter(model="test-model", token="tok")
        return adapter

    def test_calls_chat_completions_create(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "  answer text  "
        adapter._client.chat.completions.create.return_value = mock_response

        result = adapter.generate([{"role": "user", "content": "q"}], max_tokens=100, temperature=0.2)

        adapter._client.chat.completions.create.assert_called_once()
        assert result == "answer text"

    def test_passes_correct_params(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "ok"
        adapter._client.chat.completions.create.return_value = mock_response

        messages = [{"role": "user", "content": "hello"}]
        adapter.generate(messages, max_tokens=200, temperature=0.5)

        call_kwargs = adapter._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "test-model"
        assert call_kwargs["messages"] == messages
        assert call_kwargs["max_tokens"] == 200
        assert call_kwargs["temperature"] == 0.5

    def test_strips_whitespace_from_response(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "\n  trimmed  \n"
        adapter._client.chat.completions.create.return_value = mock_response

        assert adapter.generate([], 100, 0.2) == "trimmed"


# ===========================================================================
# ClaudeAdapter
# ===========================================================================

class TestClaudeAdapter:

    def _make_adapter(self):
        with patch("src.inference.adapters.claude.anthropic.Anthropic"):
            adapter = ClaudeAdapter(model="claude-test", token="tok")
        return adapter

    def test_extracts_system_message(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="answer")]
        adapter._client.messages.create.return_value = mock_response

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user",   "content": "Hello"},
        ]
        adapter.generate(messages, max_tokens=100, temperature=0.2)

        call_kwargs = adapter._client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "You are helpful."
        assert all(m["role"] != "system" for m in call_kwargs["messages"])

    def test_user_messages_passed_through(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]
        adapter._client.messages.create.return_value = mock_response

        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user",   "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user",   "content": "q2"},
        ]
        adapter.generate(messages, max_tokens=100, temperature=0.2)

        call_kwargs = adapter._client.messages.create.call_args.kwargs
        assert len(call_kwargs["messages"]) == 3

    def test_returns_empty_string_on_empty_content(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.content = []
        adapter._client.messages.create.return_value = mock_response

        result = adapter.generate([{"role": "user", "content": "q"}], 100, 0.2)
        assert result == ""

    def test_strips_whitespace_from_response(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="  trimmed  ")]
        adapter._client.messages.create.return_value = mock_response

        result = adapter.generate([{"role": "user", "content": "q"}], 100, 0.2)
        assert result == "trimmed"


# ===========================================================================
# LLMResponseGenerator
# ===========================================================================

class TestLLMResponseGenerator:

    def _make_generator(self, llm_response="The answer."):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = llm_response
        return LLMResponseGenerator(llm=mock_llm, max_tokens=200, temperature=0.2), mock_llm

    def test_returns_no_context_answer_when_chunks_empty(self):
        gen, _ = self._make_generator()
        result = gen.generate("question?", chunks=[], history=[])
        assert "couldn't find" in result.lower()

    def test_delegates_to_llm_adapter(self):
        gen, mock_llm = self._make_generator("42")
        result = gen.generate("What is the answer?", SAMPLE_CHUNKS, [])
        mock_llm.generate.assert_called_once()
        assert result == "42"

    def test_passes_max_tokens_and_temperature(self):
        gen, mock_llm = self._make_generator("ok")
        gen.generate("q", SAMPLE_CHUNKS, [])
        call_kwargs = mock_llm.generate.call_args.kwargs
        assert call_kwargs["max_tokens"] == 200
        assert call_kwargs["temperature"] == 0.2

    def test_returns_fallback_on_llm_exception(self):
        mock_llm = MagicMock()
        mock_llm.generate.side_effect = RuntimeError("API down")
        gen = LLMResponseGenerator(llm=mock_llm, max_tokens=200, temperature=0.2)
        result = gen.generate("q", SAMPLE_CHUNKS, [])
        assert "couldn't find" in result.lower()

    def test_returns_fallback_on_empty_llm_response(self):
        gen, _ = self._make_generator("")
        result = gen.generate("q", SAMPLE_CHUNKS, [])
        assert "couldn't find" in result.lower()

    def test_passes_history_to_prompt_builder(self):
        gen, mock_llm = self._make_generator("ok")
        mock_llm.generate.return_value = "ok"
        gen.generate("follow-up", SAMPLE_CHUNKS, SAMPLE_HISTORY)
        messages = mock_llm.generate.call_args.kwargs["messages"]
        contents = [m["content"] for m in messages]
        assert any("What color is the sky?" in c for c in contents)

    def test_chunks_appear_in_prompt(self):
        gen, mock_llm = self._make_generator("ok")
        gen.generate("q", SAMPLE_CHUNKS, [])
        messages = mock_llm.generate.call_args.kwargs["messages"]
        user_content = messages[-1]["content"]
        assert "The sky is blue." in user_content
        assert "Water is wet." in user_content
