"""Tests for embedding model selection and download source detection."""

from __future__ import annotations

from pathlib import Path

from hebb.embedding import catalog
from hebb.embedding.catalog import ProbeResult, model_dir_complete, workspace_model_available


def test_language_auto_english_locale() -> None:
    selection = catalog.resolve_language("auto", environ={"LANG": "en_US.UTF-8"})
    assert selection.language == "en"


def test_language_auto_chinese_locale() -> None:
    selection = catalog.resolve_language("auto", environ={"LANG": "zh_CN.UTF-8"})
    assert selection.language == "zh"


def test_language_auto_unknown_locale_defaults_multi() -> None:
    selection = catalog.resolve_language("auto", environ={"LANG": "C"})
    assert selection.language == "multi"


def test_language_auto_empty_locale_defaults_multi(monkeypatch) -> None:
    monkeypatch.setattr(catalog.locale, "getlocale", lambda: (None, None))
    selection = catalog.resolve_language("auto", environ={})
    assert selection.language == "multi"


def test_choose_default_english_model_is_small() -> None:
    # Default profile must NOT trigger a multi-GB download: en -> MiniLM (~90MB).
    spec = catalog.choose_model("en", "default")
    assert spec.model_id == "sentence-transformers/all-MiniLM-L6-v2"
    assert spec.dimension == 384


def test_choose_default_chinese_model_is_multilingual_small() -> None:
    spec = catalog.choose_model("zh", "default")
    assert spec.model_id == "intfloat/multilingual-e5-small"
    assert spec.dimension == 384


def test_choose_default_multilingual_model_is_multilingual_small() -> None:
    spec = catalog.choose_model("multi", "default")
    assert spec.model_id == "intfloat/multilingual-e5-small"
    assert spec.dimension == 384


def test_choose_fast_model_is_minilm() -> None:
    for language in ("en", "zh", "multi"):
        spec = catalog.choose_model(language, "fast")
        assert spec.model_id == "sentence-transformers/all-MiniLM-L6-v2"
        assert spec.dimension == 384


def test_choose_best_english_model_is_bge_large() -> None:
    spec = catalog.choose_model("en", "best")
    assert spec.model_id == "BAAI/bge-large-en-v1.5"
    assert spec.dimension == 1024


def test_choose_best_chinese_model_is_bge_m3() -> None:
    spec = catalog.choose_model("zh", "best")
    assert spec.model_id == "BAAI/bge-m3"
    assert spec.dimension == 1024


def test_choose_best_multilingual_model_is_bge_m3() -> None:
    spec = catalog.choose_model("multi", "best")
    assert spec.model_id == "BAAI/bge-m3"
    assert spec.dimension == 1024


class TestModelDirComplete:
    def test_missing_dir(self, tmp_path: Path) -> None:
        assert model_dir_complete(tmp_path / "nope") is False

    def test_config_without_weights_is_incomplete(self, tmp_path: Path) -> None:
        # The reported bug: an interrupted download leaves config + tokenizer
        # but no weights. Must NOT count as cached, so the download is retried.
        (tmp_path / "config.json").write_text("{}")
        (tmp_path / "tokenizer.json").write_text("{}")
        assert model_dir_complete(tmp_path) is False

    def test_weights_without_config_is_incomplete(self, tmp_path: Path) -> None:
        (tmp_path / "model.safetensors").write_bytes(b"x")
        assert model_dir_complete(tmp_path) is False

    def test_safetensors_complete(self, tmp_path: Path) -> None:
        (tmp_path / "config.json").write_text("{}")
        (tmp_path / "model.safetensors").write_bytes(b"x")
        assert model_dir_complete(tmp_path) is True

    def test_pytorch_bin_complete(self, tmp_path: Path) -> None:
        (tmp_path / "config.json").write_text("{}")
        (tmp_path / "pytorch_model.bin").write_bytes(b"x")
        assert model_dir_complete(tmp_path) is True

    def test_sharded_index_complete(self, tmp_path: Path) -> None:
        (tmp_path / "config.json").write_text("{}")
        (tmp_path / "model.safetensors.index.json").write_text("{}")
        assert model_dir_complete(tmp_path) is True

    def test_workspace_model_available_uses_completeness(self, tmp_path: Path) -> None:
        model_dir = catalog.model_cache_dir(tmp_path, "BAAI/bge-m3")
        model_dir.mkdir(parents=True)
        (model_dir / "config.json").write_text("{}")
        assert workspace_model_available(tmp_path, "BAAI/bge-m3") is False
        (model_dir / "model.safetensors").write_bytes(b"x")
        assert workspace_model_available(tmp_path, "BAAI/bge-m3") is True


class TestPrefetchIgnorePatterns:
    def test_prefetch_passes_ignore_patterns(self, tmp_path: Path, monkeypatch) -> None:
        captured: dict[str, object] = {}

        def fake_snapshot_download(**kwargs: object) -> str:
            captured.update(kwargs)
            return str(kwargs["local_dir"])

        import huggingface_hub

        monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_snapshot_download)

        catalog.prefetch_model("sentence-transformers/all-MiniLM-L6-v2", tmp_path)

        assert "ignore_patterns" in captured
        ignored = captured["ignore_patterns"]
        assert isinstance(ignored, list)
        # Redundant heavy variants are skipped.
        assert "*.onnx" in ignored
        assert "openvino/**" in ignored
        # This built-in model ships three equivalent checkpoints; retain only
        # safetensors so the advertised ~90MB download remains accurate.
        assert "pytorch_model.bin" in ignored
        assert "rust_model.ot" in ignored
        # Never use a broad pattern that would also exclude custom/BGE-M3
        # repositories whose only supported checkpoint is a .bin file.
        assert "*.bin" not in ignored
        assert "*.safetensors" not in ignored
        assert "model.safetensors" not in ignored

    def test_prefetch_keeps_bin_for_model_without_safetensors(self, tmp_path: Path, monkeypatch) -> None:
        captured: dict[str, object] = {}

        def fake_snapshot_download(**kwargs: object) -> str:
            captured.update(kwargs)
            return str(kwargs["local_dir"])

        import huggingface_hub

        monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_snapshot_download)

        catalog.prefetch_model("BAAI/bge-m3", tmp_path)

        ignored = captured["ignore_patterns"]
        assert isinstance(ignored, list)
        assert "pytorch_model.bin" not in ignored
        assert "*.bin" not in ignored


def test_region_auto_prefers_official_when_faster(monkeypatch) -> None:
    monkeypatch.setattr(
        catalog,
        "_probe_download_endpoints",
        lambda: (
            ProbeResult("global", catalog.HF_OFFICIAL_ENDPOINT, True, 20),
            ProbeResult("cn", catalog.HF_MIRROR_ENDPOINT, True, 50),
        ),
    )
    selection = catalog.resolve_region("auto")
    assert selection.region == "global"
    assert selection.hf_endpoint is None


def test_region_auto_prefers_mirror_when_faster(monkeypatch) -> None:
    monkeypatch.setattr(
        catalog,
        "_probe_download_endpoints",
        lambda: (
            ProbeResult("global", catalog.HF_OFFICIAL_ENDPOINT, True, 50),
            ProbeResult("cn", catalog.HF_MIRROR_ENDPOINT, True, 20),
        ),
    )
    selection = catalog.resolve_region("auto")
    assert selection.region == "cn"
    assert selection.hf_endpoint == catalog.HF_MIRROR_ENDPOINT


def test_region_auto_keeps_official_when_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(
        catalog,
        "_probe_download_endpoints",
        lambda: (
            ProbeResult("global", catalog.HF_OFFICIAL_ENDPOINT, False, None, "timeout"),
            ProbeResult("cn", catalog.HF_MIRROR_ENDPOINT, False, None, "timeout"),
        ),
    )
    selection = catalog.resolve_region("auto")
    assert selection.region == "global"
    assert selection.hf_endpoint is None
    assert selection.message is not None
