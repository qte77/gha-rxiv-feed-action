"""OSF preprints fetcher tests (psyArXiv): JSON:API parsing, URL building."""

import json

from src.fetchers.common import _validate_url
from src.fetchers.osf import build_osf_url, parse_osf_json

# Shape follows OSF API v2.0 (the default version): attributes.subjects is a
# list of root-to-leaf hierarchies of {id, text}; pagination via links.next.
FIXTURE = {
    "data": [
        {
            "id": "abc12_v2",
            "type": "preprints",
            "attributes": {
                "title": "Working memory\nand attention",
                "description": "Line one.\r\nLine two.",
                "date_created": "2026-10-19T08:00:00.000000",
                "date_published": "2026-10-20T09:30:00.000000",
                "version": 2,
                "subjects": [
                    [
                        {"id": "s1", "text": "Social and Behavioral Sciences"},
                        {"id": "s2", "text": "Cognitive Psychology"},
                    ],
                    [{"id": "s3", "text": "Neuroscience"}],
                    [{"id": "s1", "text": "Social and Behavioral Sciences"}],
                ],
            },
            "links": {"preprint_doi": "https://doi.org/10.31234/osf.io/abc12_v2"},
        },
        {
            "id": "xyz98_v1",
            "type": "preprints",
            "attributes": {
                "title": "Unpublished DOI",
                "description": None,
                "date_created": "2026-10-12T10:00:00.000000",
                "date_published": None,
                "version": 1,
                "subjects": [[{"id": "s4", "text": "Meta-science"}]],
            },
            "links": {"preprint_doi": None},
        },
    ],
    "links": {
        "next": "https://api.osf.io/v2/preprints/?filter%5Bprovider%5D=psyarxiv&page=2",
        "meta": {"total": 150, "per_page": 100},
    },
}


def test_parse_osf_json_maps_rows_to_biorxiv_schema():
    weekly, _ = parse_osf_json(json.dumps(FIXTURE).encode())

    assert sorted(weekly) == [(2026, 42), (2026, 43)]
    assert weekly[(2026, 43)] == [
        [
            "2026-10-20",
            43,
            "10.31234/osf.io/abc12_v2",
            2,
            "Social and Behavioral Sciences;Neuroscience",
            "Working memory and attention",
            "",
            "Line one.  Line two.",
        ]
    ]


def test_parse_osf_json_falls_back_to_created_date_and_guid():
    weekly, _ = parse_osf_json(json.dumps(FIXTURE).encode())

    (row,) = weekly[(2026, 42)]
    assert row[0] == "2026-10-12"
    assert row[2] == "xyz98"
    assert row[7] == ""


def test_parse_osf_json_filters_on_any_top_level_subject_case_insensitive():
    weekly, _ = parse_osf_json(json.dumps(FIXTURE).encode(), categories={" neuroscience "})

    assert list(weekly) == [(2026, 43)]


def test_parse_osf_json_returns_next_link_or_none():
    _, next_url = parse_osf_json(json.dumps(FIXTURE).encode())
    assert next_url == FIXTURE["links"]["next"]

    last_page = {**FIXTURE, "links": {"next": None}}
    _, next_url = parse_osf_json(json.dumps(last_page).encode())
    assert next_url is None


def test_build_osf_url_filters_provider_and_inclusive_date_window():
    url = build_osf_url("psyarxiv", "2026-10-18", "2026-10-25")

    assert url.startswith("https://api.osf.io/v2/preprints/?")
    assert "filter[provider]=psyarxiv" in url
    assert "filter[date_published][gte]=2026-10-18" in url
    assert "filter[date_published][lt]=2026-10-26" in url
    assert "page[size]=100" in url
    _validate_url(url)
