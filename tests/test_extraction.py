"""Tests for HTML/structured data extraction feature.

These tests mock the crawl4ai API to verify extraction config is built
correctly, passed through the service layer, and results are parsed properly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.models.extraction import ExtractionConfig, ExtractionSelector, JsonCssSchema, PageAction


# --- Helpers ---

def _crawl4ai_response(
    *,
    html: str = "<html><body>Hello</body></html>",
    markdown: str | dict = "# Hello",
    extracted_content: str | None = None,
    links: dict | None = None,
    images: list | None = None,
):
    """Build a fake crawl4ai API JSON response."""
    result = {
        "success": True,
        "html": html,
        "markdown": markdown,
        "media": {"images": images or []},
    }
    if extracted_content is not None:
        result["extracted_content"] = extracted_content
    if links is not None:
        result["links"] = links
    return {"results": [result]}


def _mock_httpx_response(data: dict):
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


# --- ExtractionConfig model tests ---


class TestExtractionModels:
    def test_default_config(self):
        cfg = ExtractionConfig()
        assert cfg.strategy == "raw"
        assert cfg.include_markdown is True
        assert cfg.include_html is False

    def test_css_config(self):
        cfg = ExtractionConfig(
            strategy="css",
            selectors=[
                ExtractionSelector(name="title", selector="h1"),
                ExtractionSelector(name="links", selector="a", attribute="href"),
            ],
        )
        assert cfg.strategy == "css"
        assert len(cfg.selectors) == 2
        assert cfg.selectors[1].attribute == "href"

    def test_json_css_config(self):
        schema = JsonCssSchema(
            base_selector=".card",
            fields=[
                ExtractionSelector(name="title", selector="h2"),
                ExtractionSelector(name="price", selector=".price"),
            ],
        )
        cfg = ExtractionConfig(strategy="json-css", schema=schema)
        assert cfg.strategy == "json-css"
        assert cfg.schema_.base_selector == ".card"

    def test_regex_config(self):
        cfg = ExtractionConfig(
            strategy="regex",
            patterns={"emails": r"[\w.]+@[\w.]+", "phones": r"\d{3}-\d{4}"},
        )
        assert len(cfg.patterns) == 2

    def test_ssr_wait_options(self):
        cfg = ExtractionConfig(
            wait_for_selector="#app-loaded",
            wait_timeout=15.0,
            delay_before_extract=3.0,
        )
        assert cfg.wait_for_selector == "#app-loaded"
        assert cfg.delay_before_extract == 3.0


# --- Service layer tests ---


class TestCrawlUrlExtraction:
    @pytest.mark.asyncio
    async def test_raw_extraction_returns_markdown(self):
        from app.services.crawl4ai import crawl_url

        extraction = ExtractionConfig(strategy="raw", include_markdown=True)
        response_data = _crawl4ai_response(markdown="# Page Title\nSome content")
        mock_resp = _mock_httpx_response(response_data)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await crawl_url("https://example.com", extraction=extraction)

        assert result["markdown"] == "# Page Title\nSome content"
        assert "html" not in result  # not requested

    @pytest.mark.asyncio
    async def test_raw_extraction_returns_html(self):
        from app.services.crawl4ai import crawl_url

        extraction = ExtractionConfig(include_html=True, include_markdown=False)
        response_data = _crawl4ai_response(html="<html><body>Test</body></html>")
        mock_resp = _mock_httpx_response(response_data)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await crawl_url("https://example.com", extraction=extraction)

        assert result["html"] == "<html><body>Test</body></html>"
        assert "markdown" not in result

    @pytest.mark.asyncio
    async def test_markdown_dict_handling(self):
        """crawl4ai may return markdown as a dict with sub-fields."""
        from app.services.crawl4ai import crawl_url

        extraction = ExtractionConfig(include_markdown=True)
        md_dict = {
            "raw_markdown": "# Raw",
            "markdown_with_citations": "# With Citations [1]",
            "references_markdown": "",
            "fit_markdown": "",
            "fit_html": "",
        }
        response_data = _crawl4ai_response(markdown=md_dict)
        mock_resp = _mock_httpx_response(response_data)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await crawl_url("https://example.com", extraction=extraction)

        assert result["markdown"] == "# With Citations [1]"

    @pytest.mark.asyncio
    async def test_regex_extraction(self):
        from app.services.crawl4ai import crawl_url

        extraction = ExtractionConfig(
            strategy="regex",
            patterns={"emails": r"[\w.]+@[\w.]+\.\w+"},
            include_markdown=False,
        )
        response_data = _crawl4ai_response(
            html="<p>Contact us at info@example.com or support@test.org</p>"
        )
        mock_resp = _mock_httpx_response(response_data)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await crawl_url("https://example.com", extraction=extraction)

        assert "extracted_data" in result
        assert "info@example.com" in result["extracted_data"]["emails"]
        assert "support@test.org" in result["extracted_data"]["emails"]

    @pytest.mark.asyncio
    async def test_links_extraction(self):
        from app.services.crawl4ai import crawl_url

        extraction = ExtractionConfig(include_links=True, include_markdown=False)
        response_data = _crawl4ai_response(
            links={
                "internal": [{"href": "/about", "text": "About"}],
                "external": [{"href": "https://other.com", "text": "Other"}],
            }
        )
        mock_resp = _mock_httpx_response(response_data)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await crawl_url("https://example.com", extraction=extraction)

        assert len(result["links"]) == 2

    @pytest.mark.asyncio
    async def test_css_strategy_builds_payload(self):
        """Verify CSS extraction strategy is included in crawl4ai payload."""
        from app.services.crawl4ai import crawl_url

        extraction = ExtractionConfig(
            strategy="css",
            selectors=[ExtractionSelector(name="title", selector="h1")],
            include_markdown=False,
        )
        response_data = _crawl4ai_response()
        mock_resp = _mock_httpx_response(response_data)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await crawl_url("https://example.com", extraction=extraction)

            # Check the payload sent to crawl4ai
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
            crawler_config = payload["crawler_config"]["params"]
            assert "extraction_strategy" in crawler_config
            assert crawler_config["extraction_strategy"]["type"] == "CssExtractionStrategy"

    @pytest.mark.asyncio
    async def test_wait_for_selector_in_payload(self):
        """Verify SSR wait_for_selector is passed to crawl4ai."""
        from app.services.crawl4ai import crawl_url

        extraction = ExtractionConfig(
            wait_for_selector="#app-content",
            delay_before_extract=3.0,
            include_markdown=False,
        )
        response_data = _crawl4ai_response()
        mock_resp = _mock_httpx_response(response_data)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await crawl_url("https://example.com", extraction=extraction)

            call_args = mock_client.post.call_args
            payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
            crawler_config = payload["crawler_config"]["params"]
            assert crawler_config["wait_for"] == "css:#app-content"
            assert crawler_config["delay_before_return_html"] == 3.0

    @pytest.mark.asyncio
    async def test_no_extraction_preserves_existing_behavior(self):
        """When no extraction config is provided, result has no extraction fields."""
        from app.services.crawl4ai import crawl_url

        response_data = _crawl4ai_response(
            images=[{"src": "https://example.com/img.jpg", "alt": "test"}]
        )
        mock_resp = _mock_httpx_response(response_data)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await crawl_url("https://example.com")

        assert "markdown" not in result
        assert "html" not in result
        assert "extracted_data" not in result
        assert len(result["images"]) == 1

    @pytest.mark.asyncio
    async def test_extraction_alongside_images(self):
        """Extraction and image discovery work together."""
        from app.services.crawl4ai import crawl_url

        extraction = ExtractionConfig(include_markdown=True)
        response_data = _crawl4ai_response(
            markdown="# Page",
            images=[{"src": "https://example.com/photo.jpg", "alt": "photo"}],
        )
        mock_resp = _mock_httpx_response(response_data)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await crawl_url("https://example.com", extraction=extraction)

        assert result["markdown"] == "# Page"
        assert len(result["images"]) == 1


# --- CLI tests ---


class TestCLIExtraction:
    def test_build_extraction_none_when_not_specified(self):
        from crawl_images import _build_extraction

        args = MagicMock()
        args.extract = None
        assert _build_extraction(args) is None

    def test_build_extraction_raw(self):
        from crawl_images import _build_extraction

        args = MagicMock()
        args.extract = "raw"
        args.selector = None
        args.json_schema = None
        args.regex = None
        args.wait_for = None
        args.wait_timeout = 10.0
        args.delay_before_extract = None
        args.action = None
        args.include_html = True
        args.include_markdown = True
        cfg = _build_extraction(args)
        assert cfg.strategy == "raw"
        assert cfg.include_html is True

    def test_build_extraction_css_selectors(self):
        from crawl_images import _build_extraction

        args = MagicMock()
        args.extract = "css"
        args.selector = ["title:h1", "links:a.nav@href"]
        args.json_schema = None
        args.regex = None
        args.action = None
        args.wait_for = None
        args.wait_timeout = 10.0
        args.delay_before_extract = None
        args.include_html = False
        args.include_markdown = False
        cfg = _build_extraction(args)
        assert cfg.strategy == "css"
        assert len(cfg.selectors) == 2
        assert cfg.selectors[0].name == "title"
        assert cfg.selectors[0].selector == "h1"
        assert cfg.selectors[0].attribute is None
        assert cfg.selectors[1].name == "links"
        assert cfg.selectors[1].selector == "a.nav"
        assert cfg.selectors[1].attribute == "href"

    def test_build_extraction_regex(self):
        from crawl_images import _build_extraction

        args = MagicMock()
        args.extract = "regex"
        args.selector = None
        args.json_schema = None
        args.regex = [r"emails:[\w.]+@[\w.]+"]
        args.action = None
        args.wait_for = None
        args.wait_timeout = 10.0
        args.delay_before_extract = None
        args.include_html = False
        args.include_markdown = False
        cfg = _build_extraction(args)
        assert cfg.strategy == "regex"
        assert r"[\w.]+@[\w.]+" in cfg.patterns["emails"]

    def test_build_extraction_json_schema(self, tmp_path):
        from crawl_images import _build_extraction

        schema_file = tmp_path / "schema.json"
        schema_file.write_text(json.dumps({
            "base_selector": ".product",
            "fields": [
                {"name": "title", "selector": "h2"},
                {"name": "price", "selector": ".price"},
            ],
        }))
        args = MagicMock()
        args.extract = "json-css"
        args.selector = None
        args.json_schema = str(schema_file)
        args.regex = None
        args.action = None
        args.wait_for = "#loaded"
        args.wait_timeout = 15.0
        args.delay_before_extract = 2.0
        args.include_html = False
        args.include_markdown = False
        cfg = _build_extraction(args)
        assert cfg.strategy == "json-css"
        assert cfg.schema_.base_selector == ".product"
        assert cfg.wait_for_selector == "#loaded"
        assert cfg.delay_before_extract == 2.0

    def test_build_extraction_with_actions(self):
        from crawl_images import _build_extraction

        args = MagicMock()
        args.extract = "raw"
        args.selector = None
        args.json_schema = None
        args.regex = None
        args.action = ["click:.tab-specs", "wait:.spec-table", "js:document.querySelector('.expand').click()"]
        args.wait_for = None
        args.wait_timeout = 10.0
        args.delay_before_extract = None
        args.include_html = True
        args.include_markdown = True
        cfg = _build_extraction(args)
        assert cfg.pre_actions is not None
        assert len(cfg.pre_actions) == 3
        assert cfg.pre_actions[0].action == "click"
        assert cfg.pre_actions[0].selector == ".tab-specs"
        assert cfg.pre_actions[1].action == "wait"
        assert cfg.pre_actions[1].selector == ".spec-table"
        assert cfg.pre_actions[2].action == "js"
        assert "expand" in cfg.pre_actions[2].value


# --- PageAction and pre_actions tests ---


class TestPageActions:
    def test_page_action_model(self):
        act = PageAction(action="click", selector=".tab")
        assert act.action == "click"
        assert act.wait_after == 1000

    def test_page_action_js(self):
        act = PageAction(action="js", value="document.title='test'")
        assert act.value == "document.title='test'"

    @pytest.mark.asyncio
    async def test_pre_actions_generate_js_in_payload(self):
        """Pre-actions should inject JS code into crawl4ai payload."""
        from app.services.crawl4ai import crawl_url

        extraction = ExtractionConfig(
            include_markdown=False,
            pre_actions=[
                PageAction(action="click", selector=".specs-tab", wait_after=2000),
                PageAction(action="click", selector=".expand-all", wait_after=1000),
            ],
        )
        response_data = _crawl4ai_response()
        mock_resp = _mock_httpx_response(response_data)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await crawl_url("https://example.com", extraction=extraction)

            call_args = mock_client.post.call_args
            payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
            crawler_config = payload["crawler_config"]["params"]
            assert "js_code" in crawler_config
            assert ".specs-tab" in crawler_config["js_code"]
            assert ".expand-all" in crawler_config["js_code"]
            # Delay should be auto-calculated: (2000 + 1000) / 1000 + 2.0 = 5.0
            assert crawler_config["delay_before_return_html"] >= 5.0

    @pytest.mark.asyncio
    async def test_pre_actions_cumulative_timing(self):
        """Actions should have staggered setTimeout delays."""
        from app.services.crawl4ai import crawl_url

        extraction = ExtractionConfig(
            include_markdown=False,
            pre_actions=[
                PageAction(action="click", selector="#tab1", wait_after=1500),
                PageAction(action="click", selector="#tab2", wait_after=1500),
            ],
        )
        response_data = _crawl4ai_response()
        mock_resp = _mock_httpx_response(response_data)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await crawl_url("https://example.com", extraction=extraction)

            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            js_code = payload["crawler_config"]["params"]["js_code"]
            # First action at 0ms, second at 1500ms
            assert "setTimeout(function() {" in js_code
            assert "}, 0);" in js_code
            assert "}, 1500);" in js_code
