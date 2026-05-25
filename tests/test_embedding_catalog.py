"""Tests for embedding model selection and download source detection."""

from __future__ import annotations

from hebb.embedding import catalog
from hebb.embedding.catalog import ProbeResult


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


def test_choose_default_english_model() -> None:
    spec = catalog.choose_model("en", "default")
    assert spec.model_id == "BAAI/bge-large-en-v1.5"
    assert spec.dimension == 1024


def test_choose_default_multilingual_model() -> None:
    spec = catalog.choose_model("multi", "default")
    assert spec.model_id == "BAAI/bge-m3"
    assert spec.dimension == 1024


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
