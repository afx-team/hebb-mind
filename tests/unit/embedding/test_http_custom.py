"""Unit tests for the custom HTTP embedding provider."""

from __future__ import annotations

import pytest

from hebb.embedding.http_custom import (
    CustomHttpEmbedder,
    extract_vectors,
    parse_headers,
    render_body,
)


class TestParseHeaders:
    def test_empty_and_none(self) -> None:
        assert parse_headers(None) == {}
        assert parse_headers("") == {}
        assert parse_headers("   ") == {}

    def test_valid_object(self) -> None:
        headers = parse_headers('{"Authorization": "Bearer x", "X-Num": 3}')
        # values are coerced to str so httpx accepts them
        assert headers == {"Authorization": "Bearer x", "X-Num": "3"}

    def test_invalid_json(self) -> None:
        with pytest.raises(ValueError, match="not valid JSON"):
            parse_headers("{not json}")

    def test_non_object(self) -> None:
        with pytest.raises(ValueError, match="must be a JSON object"):
            parse_headers('["a", "b"]')


class TestRenderBody:
    def test_input_token_batches(self) -> None:
        payload, batched = render_body('{"model": "m", "input": {{input}}}', texts=["a", "b"])
        assert batched is True
        assert payload == {"model": "m", "input": ["a", "b"]}

    def test_text_token_single(self) -> None:
        payload, batched = render_body('{"text": {{text}}}', texts=["hello"])
        assert batched is False
        assert payload == {"text": "hello"}

    def test_text_token_requires_single(self) -> None:
        with pytest.raises(ValueError, match="exactly one text"):
            render_body('{"text": {{text}}}', texts=["a", "b"])

    def test_missing_placeholder(self) -> None:
        with pytest.raises(ValueError, match="must contain"):
            render_body('{"model": "m"}', texts=["a"])

    def test_escapes_special_chars(self) -> None:
        # Quotes/newlines in the text must not break the rendered JSON.
        payload, _ = render_body('{"text": {{text}}}', texts=['he said "hi"\nbye'])
        assert payload == {"text": 'he said "hi"\nbye'}

    def test_invalid_rendered_json(self) -> None:
        with pytest.raises(ValueError, match="not valid JSON"):
            render_body('{"input": {{input}}', texts=["a"])  # missing closing brace


class TestExtractVectors:
    def test_openai_shape_wildcard(self) -> None:
        resp = {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}
        assert extract_vectors(resp, "data.*.embedding") == [[0.1, 0.2], [0.3, 0.4]]

    def test_single_indexed(self) -> None:
        resp = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
        assert extract_vectors(resp, "data.0.embedding") == [[0.1, 0.2, 0.3]]

    def test_flat_vector(self) -> None:
        resp = {"embedding": [1, 2, 3]}
        assert extract_vectors(resp, "embedding") == [[1.0, 2.0, 3.0]]

    def test_top_level_list_of_vectors(self) -> None:
        resp = {"embeddings": [[1, 2], [3, 4]]}
        assert extract_vectors(resp, "embeddings.*") == [[1.0, 2.0], [3.0, 4.0]]

    def test_missing_key(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            extract_vectors({"data": []}, "result.embedding")

    def test_not_a_vector(self) -> None:
        with pytest.raises(ValueError, match="did not resolve"):
            extract_vectors({"data": "oops"}, "data")

    def test_index_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            extract_vectors({"data": [{"embedding": [1.0]}]}, "data.5.embedding")


def _stub_request(embedder: CustomHttpEmbedder, response: object) -> None:
    """Replace the network call with a canned response (or a callable)."""

    async def _fake(payload: object) -> object:
        return response(payload) if callable(response) else response

    embedder._request = _fake  # type: ignore[assignment]


@pytest.mark.asyncio
class TestCustomHttpEmbedder:
    async def test_batch_mode(self) -> None:
        emb = CustomHttpEmbedder(
            method="POST",
            url="https://x/embed",
            headers={},
            body_template='{"input": {{input}}}',
            response_path="data.*.embedding",
        )
        _stub_request(
            emb,
            lambda payload: {"data": [{"embedding": [float(i)]} for i in range(len(payload["input"]))]},
        )
        out = await emb.embed_batch(["a", "b", "c"])
        # F4: vectors are L2-normalized, so each single-component vector [n]
        # collapses to unit magnitude ([1.0]); [0.0] has no direction and stays.
        assert out == [[0.0], [1.0], [1.0]]

    async def test_batch_count_mismatch_raises(self) -> None:
        emb = CustomHttpEmbedder(
            method="POST",
            url="https://x/embed",
            headers={},
            body_template='{"input": {{input}}}',
        )
        _stub_request(emb, {"data": [{"embedding": [0.1]}]})  # only one vector for two inputs
        with pytest.raises(ValueError, match="returned 1 vectors for 2 inputs"):
            await emb.embed_batch(["a", "b"])

    async def test_per_text_mode_loops(self) -> None:
        emb = CustomHttpEmbedder(
            method="POST",
            url="https://x/embed",
            headers={},
            body_template='{"text": {{text}}}',
            response_path="embedding",
        )
        assert emb._per_text is True
        _stub_request(emb, lambda payload: {"embedding": [float(len(payload["text"]))]})
        out = await emb.embed_batch(["a", "bbb"])
        # F4: per-text vectors are L2-normalized; [1.0] and [3.0] both become [1.0].
        assert out == [[1.0], [1.0]]

    async def test_embed_single(self) -> None:
        emb = CustomHttpEmbedder(
            method="POST",
            url="https://x/embed",
            headers={},
            body_template='{"input": {{input}}}',
        )
        _stub_request(emb, {"data": [{"embedding": [0.5, 0.6]}]})
        # F4: the returned vector is L2-normalized ([0.5, 0.6] / |[0.5, 0.6]|).
        assert await emb.embed("hi") == pytest.approx([0.6401843996644799, 0.7682212795973759])

    async def test_empty_batch(self) -> None:
        emb = CustomHttpEmbedder(
            method="POST",
            url="https://x/embed",
            headers={},
            body_template='{"input": {{input}}}',
        )
        assert await emb.embed_batch([]) == []

    async def test_requires_placeholder_at_construction(self) -> None:
        with pytest.raises(ValueError, match="must contain"):
            CustomHttpEmbedder(method="POST", url="https://x", headers={}, body_template='{"model": "m"}')

    async def test_set_dimension(self) -> None:
        emb = CustomHttpEmbedder(
            method="POST",
            url="https://x/embed",
            headers={},
            body_template='{"input": {{input}}}',
            dimension=0,
        )
        emb.set_dimension(384)
        assert emb.dimension == 384
