"""Fetches raw report text from Confluence Cloud, in three shapes:

- ConfluenceSource: every page in one or more spaces (CQL `space = ...`).
- ConfluenceTreeSource: every descendant of one page, recursively (CQL `ancestor = ...`)
  - the "mother page" case: point it at a page and it pulls in the whole subtree below.
- ConfluenceSinglePageSource: exactly one page, no search, no recursion.
"""

from __future__ import annotations

import html
import os
import re
from abc import abstractmethod
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

import requests

from mosaiq.model import RawDocument
from mosaiq.sources.base import Source

CREDENTIALS_FILENAME = ".mosaiq-credentials"
PAGE_SIZE = 50


class _ConfluenceSourceBase(Source):
    """Shared auth + HTTP plumbing. Auth resolution order: constructor args >
    MOSAIQ_CONFLUENCE_EMAIL / MOSAIQ_CONFLUENCE_TOKEN env vars > a local
    .mosaiq-credentials file (email on line 1, API token on line 2 - gitignored,
    never committed). The credentials file is looked up in `credentials_dir` (default:
    the current working directory) - when built via a --config file, config.py passes
    that config's own folder, so the credentials file can live next to it regardless of
    where the command is actually run from.
    """

    def __init__(
        self,
        base_url: str,
        email: str | None = None,
        api_token: str | None = None,
        credentials_dir: str | Path | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.email, self.api_token = _resolve_credentials(email, api_token, credentials_dir)

    @abstractmethod
    def discover(self) -> Iterable[RawDocument]: ...

    def _get(self, path: str, params: dict | None = None) -> dict:
        response = requests.get(
            f"{self.base_url}{path}",
            params=params,
            auth=(self.email, self.api_token),
            headers={"Accept": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _to_raw_document(self, page: dict) -> RawDocument:
        storage_html = page.get("body", {}).get("storage", {}).get("value", "")
        last_updated = page.get("history", {}).get("lastUpdated", {}).get("when")
        webui = page.get("_links", {}).get("webui")
        return RawDocument(
            text=html_storage_to_text(storage_html),
            origin_id=page["id"],
            origin_url=f"{self.base_url}{webui}" if webui else None,
            fetched_at=_parse_confluence_timestamp(last_updated),
        )

    def _search(self, cql: str) -> Iterable[RawDocument]:
        # The content search endpoint hands back a cursor-based "next" link, not a
        # classic offset - manually incrementing start=0,50,100... against it doesn't
        # reliably terminate. Follow _links.next verbatim instead; its absence means
        # this was the last page.
        path = "/rest/api/content/search"
        params: dict | None = {
            "cql": cql,
            "expand": "body.storage,history.lastUpdated",
            "limit": PAGE_SIZE,
        }
        while True:
            response = self._get(path, params)
            for page in response["results"]:
                yield self._to_raw_document(page)
            next_link = response.get("_links", {}).get("next")
            if not next_link:
                break
            path = next_link
            params = None


class ConfluenceSource(_ConfluenceSourceBase):
    """Every page in one or more Confluence spaces."""

    def __init__(
        self,
        base_url: str,
        space_keys: list[str],
        email: str | None = None,
        api_token: str | None = None,
        extra_cql: str | None = None,
        credentials_dir: str | Path | None = None,
    ):
        super().__init__(base_url, email, api_token, credentials_dir)
        self.space_keys = space_keys
        self.extra_cql = extra_cql

    def discover(self) -> Iterable[RawDocument]:
        space_clause = " OR ".join(f'space = "{key}"' for key in self.space_keys)
        cql = f"type = page AND ({space_clause})"
        if self.extra_cql:
            cql += f" AND ({self.extra_cql})"
        return self._search(cql)


class ConfluenceTreeSource(_ConfluenceSourceBase):
    """Every descendant of one Confluence page, recursively - the "mother page" case.
    Pulling in the whole subtree, however deep, is the point of pointing at a mother
    page in the first place, so there's no separate flag for "just the direct
    children" - use ConfluenceSinglePageSource for "just this one page" instead."""

    def __init__(
        self,
        base_url: str,
        page_id: str | int,
        email: str | None = None,
        api_token: str | None = None,
        credentials_dir: str | Path | None = None,
    ):
        super().__init__(base_url, email, api_token, credentials_dir)
        self.page_id = str(page_id)

    def discover(self) -> Iterable[RawDocument]:
        return self._search(f"ancestor={self.page_id} and type=page")


class ConfluenceSinglePageSource(_ConfluenceSourceBase):
    """Exactly one page - no search, no recursion. For adding one extra page that
    isn't under any mother page, or excluding one via a sibling exclude list."""

    def __init__(
        self,
        base_url: str,
        page_id: str | int,
        email: str | None = None,
        api_token: str | None = None,
        credentials_dir: str | Path | None = None,
    ):
        super().__init__(base_url, email, api_token, credentials_dir)
        self.page_id = str(page_id)

    def discover(self) -> Iterable[RawDocument]:
        page = self._get(
            f"/rest/api/content/{self.page_id}",
            params={"expand": "body.storage,history.lastUpdated"},
        )
        yield self._to_raw_document(page)


def _resolve_credentials(
    email: str | None, api_token: str | None, credentials_dir: str | Path | None = None
) -> tuple[str, str]:
    email = email or os.environ.get("MOSAIQ_CONFLUENCE_EMAIL")
    api_token = api_token or os.environ.get("MOSAIQ_CONFLUENCE_TOKEN")
    if email and api_token:
        return email, api_token

    credentials_file = Path(credentials_dir or ".") / CREDENTIALS_FILENAME
    if credentials_file.exists():
        lines = credentials_file.read_text(encoding="utf-8-sig").splitlines()
        if len(lines) >= 2:
            return lines[0].strip(), lines[1].strip()

    raise RuntimeError(
        "Confluence credentials not found. Pass --confluence-email/--confluence-token, "
        "set MOSAIQ_CONFLUENCE_EMAIL/MOSAIQ_CONFLUENCE_TOKEN, or create .mosaiq-credentials "
        "(email on line 1, API token on line 2 - gitignored, never commit this file)."
    )


def _parse_confluence_timestamp(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


_PLAIN_TEXT_MACRO_CDATA_RE = re.compile(
    # Non-greedy .*? (not \s*) between the opening macro tag and <ac:plain-text-body>:
    # a macro can carry <ac:parameter> children first (e.g. a "wide" display-width
    # setting), and strict whitespace-only matching misses those entirely.
    r"<ac:structured-macro[^>]*>.*?<ac:plain-text-body>\s*<!\[CDATA\[(.*?)\]\]>\s*</ac:plain-text-body>.*?</ac:structured-macro>",
    re.DOTALL,
)
_BLOCK_OPEN_RE = re.compile(r"<(p|div|li|h[1-6]|tr)[^>]*>", re.IGNORECASE)
_BLOCK_CLOSE_RE = re.compile(r"</(p|div|li|h[1-6]|tr)>|<br\s*/?>", re.IGNORECASE)
_BOLD_RE = re.compile(r"</?(strong|b)>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def html_storage_to_text(storage_html: str) -> str:
    """Best-effort Confluence storage-format -> plain text.

    A raw report pasted into any macro with a plain-text body (the common case: a
    'code' or 'markdown' macro wrapping a diagnostic tool's output pasted verbatim) is
    recovered byte-for-byte from its CDATA, regardless of which macro name wraps it -
    matching on the generic <ac:plain-text-body><![CDATA[...]]> shape rather than a
    specific macro name avoids missing future macro types that use the same wrapper.
    Without this, the generic tag-stripping fallback below mistakes the literal
    "<![CDATA[" text for an opening HTML tag and silently deletes everything up to the
    next ">" character it finds inside the pasted content itself.

    Anything else (a page authored as rich/markdown-flavored text with no plain-text
    macro) is flattened: block tags become newlines, bold becomes '**' markers, so the
    bundled parsers still have a shot at recognizing it. This is intentionally
    approximate for that fallback path - tune the regexes here against real pages as
    format drift shows up.
    """
    plain_text_match = _PLAIN_TEXT_MACRO_CDATA_RE.search(storage_html)
    if plain_text_match:
        return html.unescape(plain_text_match.group(1))

    text = _BOLD_RE.sub("**", storage_html)
    text = _BLOCK_OPEN_RE.sub("\n", text)
    text = _BLOCK_CLOSE_RE.sub("\n", text)
    text = _TAG_RE.sub("", text)
    return html.unescape(text)
