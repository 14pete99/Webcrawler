"""Extraction strategy models for HTML/structured data scraping."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExtractionSelector(BaseModel):
    """A single CSS selector extraction rule."""

    name: str = Field(description="Field name in output")
    selector: str = Field(description="CSS selector")
    attribute: str | None = Field(
        default=None,
        description="HTML attribute to extract (e.g. 'href', 'src'); None = text content",
    )
    multiple: bool = Field(
        default=True, description="Return list vs single value"
    )


class JsonCssSchema(BaseModel):
    """Schema for JSON-CSS extraction (repeating blocks like cards/rows)."""

    base_selector: str = Field(
        description="CSS selector for each repeating item"
    )
    fields: list[ExtractionSelector] = Field(
        description="Fields to extract from each item"
    )


class PageAction(BaseModel):
    """A single pre-extraction page interaction."""

    action: Literal["click", "wait", "scroll", "js"] = Field(
        description="Action type: click a selector, wait for selector/time, scroll, or run JS",
    )
    selector: str | None = Field(
        default=None,
        description="CSS selector for click/wait actions",
    )
    value: str | None = Field(
        default=None,
        description="JS code for 'js' action, or milliseconds for 'wait' without selector",
    )
    wait_after: int = Field(
        default=1000,
        description="Milliseconds to wait after this action completes",
    )


class ExtractionConfig(BaseModel):
    """Extraction configuration attached to a crawl request."""

    strategy: Literal["raw", "css", "json-css", "regex"] = Field(
        default="raw",
        description="Extraction strategy to use",
    )

    # For strategy="css"
    selectors: list[ExtractionSelector] | None = Field(
        default=None, description="CSS selector rules (strategy='css')"
    )

    # For strategy="json-css"
    schema_: JsonCssSchema | None = Field(
        default=None,
        alias="schema",
        description="JSON-CSS schema definition (strategy='json-css')",
    )

    # For strategy="regex"
    patterns: dict[str, str] | None = Field(
        default=None,
        description="Name -> regex pattern mapping (strategy='regex')",
    )

    # Pre-extraction page interactions (click tabs, expand sections, etc.)
    pre_actions: list[PageAction] | None = Field(
        default=None,
        description="Actions to perform before extracting (click tabs, expand sections)",
    )

    # SSR / dynamic content wait options
    wait_for_selector: str | None = Field(
        default=None,
        description="CSS selector to wait for before extracting (SSR support)",
    )
    wait_timeout: float = Field(
        default=10.0, description="Wait timeout in seconds"
    )
    delay_before_extract: float | None = Field(
        default=None,
        description="Extra delay in seconds for JS frameworks to finish rendering",
    )

    # Content options
    include_html: bool = Field(
        default=False, description="Include raw HTML in output"
    )
    include_markdown: bool = Field(
        default=True, description="Include markdown in output"
    )
    include_links: bool = Field(
        default=False, description="Include extracted links"
    )

    model_config = {"populate_by_name": True}
