from unittest.mock import MagicMock, patch

from mosaiq.sources.confluence import (
    ConfluenceSinglePageSource,
    ConfluenceTreeSource,
    html_storage_to_text,
)

ENV_PATCH = {"MOSAIQ_CONFLUENCE_EMAIL": "test@example.com", "MOSAIQ_CONFLUENCE_TOKEN": "fake-token"}


def _mock_response(json_body):
    response = MagicMock()
    response.json.return_value = json_body
    response.raise_for_status.return_value = None
    return response


def _page(page_id: str) -> dict:
    return {
        "id": page_id,
        "body": {"storage": {"value": f"<p>Customer: Test {page_id}</p>"}},
        "history": {"lastUpdated": {"when": "2026-01-01T00:00:00.000Z"}},
        "_links": {"webui": f"/pages/{page_id}"},
    }


def test_code_macro_cdata_is_recovered_verbatim():
    storage_html = (
        '<ac:structured-macro ac:name="code" ac:schema-version="1">'
        "<ac:plain-text-body>"
        "<![CDATA[####### REPORT INFO #######\nCustomer: Acme Nordics\nCPU cores: 8]]>"
        "</ac:plain-text-body>"
        "</ac:structured-macro>"
    )
    text = html_storage_to_text(storage_html)
    assert text == "####### REPORT INFO #######\nCustomer: Acme Nordics\nCPU cores: 8"


def test_markdown_macro_cdata_is_recovered_verbatim():
    # Regression test: a different macro name ("markdown" instead of "code") wrapping
    # the same <ac:plain-text-body><![CDATA[...]]> shape used to fall through to the
    # tag-stripping fallback, which mistook the literal "<![CDATA[" text for an
    # opening tag and silently deleted everything up to the first ">" it found inside
    # the pasted content - in practice, the first "->" arrow deep in a real report.
    storage_html = (
        '<ac:structured-macro ac:name="markdown" ac:schema-version="1">'
        "<ac:plain-text-body>"
        "<![CDATA[\n## Report Info\n\n**Customer:** Acme Nordics\n"
        "**Disk Capacity:** C: -> 76.5 GB / 149.7 GB]]>"
        "</ac:plain-text-body>"
        "</ac:structured-macro>"
    )
    text = html_storage_to_text(storage_html)
    assert text == (
        "\n## Report Info\n\n**Customer:** Acme Nordics\n"
        "**Disk Capacity:** C: -> 76.5 GB / 149.7 GB"
    )


def test_code_macro_with_parameter_children_is_recovered_verbatim():
    # Regression test: a macro can carry <ac:parameter> children (e.g. a "wide"
    # display-width setting) before <ac:plain-text-body> - a strict whitespace-only
    # gap between the opening tag and <ac:plain-text-body> misses this macro
    # entirely, falling through to the same CDATA-truncation bug as above.
    storage_html = (
        '<ac:structured-macro ac:name="code" ac:schema-version="1">'
        '<ac:parameter ac:name="breakoutMode">wide</ac:parameter>'
        '<ac:parameter ac:name="breakoutWidth">1800</ac:parameter>'
        "<ac:plain-text-body>"
        "<![CDATA[Customer: Acme Nordics\nDisk Capacity: C: -> 76.5 GB]]>"
        "</ac:plain-text-body>"
        "</ac:structured-macro>"
    )
    text = html_storage_to_text(storage_html)
    assert text == "Customer: Acme Nordics\nDisk Capacity: C: -> 76.5 GB"


def test_rich_text_fallback_flattens_block_tags_and_bold():
    storage_html = (
        "<h2>Report Info</h2>"
        "<p><strong>Customer:</strong> Contoso Labs</p>"
        "<p><strong>CPU cores:</strong> 12</p>"
    )
    text = html_storage_to_text(storage_html)
    assert "**Customer:** Contoso Labs" in text
    assert "**CPU cores:** 12" in text
    assert "Report Info" in text


def test_html_entities_are_decoded():
    storage_html = "<p>Connectors in actual use:</p><p>web &amp; fileserver</p>"
    text = html_storage_to_text(storage_html)
    assert "web & fileserver" in text


@patch.dict("os.environ", ENV_PATCH)
@patch("mosaiq.sources.confluence.requests.get")
def test_tree_source_queries_by_ancestor_and_follows_cursor_pagination(mock_get):
    # The real API hands back a cursor-based _links.next, not a classic offset -
    # pagination must follow that link verbatim, not compute start=0,50,100...
    next_link = "/rest/api/content/search?next=true&cursor=abc123&cql=ancestor%3D999"
    mock_get.side_effect = [
        _mock_response({"results": [_page("1"), _page("2")], "_links": {"next": next_link}}),
        _mock_response({"results": [_page("3")], "_links": {}}),  # no "next" -> stop
    ]

    documents = list(ConfluenceTreeSource(base_url="https://x.atlassian.net/wiki", page_id=999).discover())

    assert [d.origin_id for d in documents] == ["1", "2", "3"]
    first_call_params = mock_get.call_args_list[0].kwargs["params"]
    assert first_call_params["cql"] == "ancestor=999 and type=page"
    # second call must hit the cursor URL directly, with no extra params appended
    assert mock_get.call_args_list[1].args[0] == f"https://x.atlassian.net/wiki{next_link}"
    assert mock_get.call_args_list[1].kwargs["params"] is None


@patch.dict("os.environ", ENV_PATCH)
@patch("mosaiq.sources.confluence.requests.get")
def test_single_page_source_fetches_one_page_by_id(mock_get):
    mock_get.return_value = _mock_response(_page("555"))

    documents = list(
        ConfluenceSinglePageSource(base_url="https://x.atlassian.net/wiki", page_id=555).discover()
    )

    assert len(documents) == 1
    assert documents[0].origin_id == "555"
    called_url = mock_get.call_args.args[0]
    assert called_url.endswith("/rest/api/content/555")
