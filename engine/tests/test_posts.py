from datetime import UTC, datetime

import pytest

from engine.feeds.posts import (
    html_text,
    mirror_post,
    parse_status_id,
    plain_text,
    split_quote,
    status_time,
)


def test_post_time_comes_from_the_status_id() -> None:
    # CNN's created_at for this post is 2026-10-02T06:29:16.875Z, 2 ms later.
    assert status_time("117369900687288624") == datetime(2026, 10, 2, 6, 29, 16, 873000, UTC)


@pytest.mark.parametrize("value", ["", "abc", "12345", "https://truthsocial.com/x"])
def test_status_ids_are_checked(value: str) -> None:
    with pytest.raises(ValueError, match="not a Truth Social status id"):
        parse_status_id(value)


def test_mirror_kinds() -> None:
    url = "https://truthsocial.com/users/realDonaldTrump/statuses/117367780569149238"
    rt_url = mirror_post("117369900687288624", f"RT: {url}", True, {})
    assert (rt_url.kind, rt_url.points_to, rt_url.not_scored) == (
        "repost",
        "117367780569149238",
        "repost",
    )

    rt_handle = mirror_post(
        "116501828501933903", "RT @realDonaldTrumpIt is my Great Honor", False, {}
    )
    assert (rt_handle.kind, rt_handle.points_to, rt_handle.not_scored) == ("repost", None, "repost")

    bare = mirror_post(
        "117307289681145880",
        "https://truthsocial.com/@realDonaldTrump/117304284426928910",
        False,
        {},
    )
    assert (bare.kind, bare.points_to, bare.text, bare.not_scored) == (
        "quote",
        "117304284426928910",
        "",
        "no_text",
    )

    marked = mirror_post(
        "117307289681145880",
        "Read this!\nRE: https://truthsocial.com/@realDonaldTrump/117304284426928910",
        False,
        {},
    )
    assert (marked.kind, marked.points_to, marked.text, marked.not_scored) == (
        "quote",
        "117304284426928910",
        "Read this!",
        None,
    )

    post = mirror_post(
        "117371353802794328", "Big news. LINK HERE: https://rumble.com/v5", False, {}
    )
    assert (post.kind, post.points_to, post.not_scored) == ("post", None, None)

    media_only = mirror_post("117368266436035432", "", True, {})
    assert (media_only.kind, media_only.not_scored) == ("post", "no_text")


def test_a_link_inside_a_post_is_not_a_quote() -> None:
    text = "Great piece: https://truthsocial.com/@breitbartnews/117305295296594991 Read it!"
    assert split_quote(text) == (text, None)


def test_plain_text_repairs_mojibake_and_entities() -> None:
    cnn = "Stocks &amp; NASDAQ! CRYPTO, \u00e2\x80\x9cThrough the Roof.\u00e2\x80\x9d"
    assert plain_text(cnn) == "Stocks & NASDAQ! CRYPTO, \u201cThrough the Roof.\u201d"
    assert plain_text("Florida!\n\xa0\nWilton  ") == "Florida!\n\nWilton"
    assert plain_text("Tariffs &amp;amp;amp; trade") == "Tariffs & trade"  # escaped twice
    assert plain_text("GOD BLESS HIM!\u00c2") == "GOD BLESS HIM!"  # a trimmed "\u00c2\xa0"


def test_only_cnn_text_is_repaired() -> None:
    """ "É" followed by a no-break space reads as mojibake; in HTML text it is correct."""
    assert html_text("<p>CAF\u00c9&nbsp;OWNERS</p>") == "CAF\u00c9 OWNERS"


def test_html_text_keeps_line_breaks_and_drops_tags() -> None:
    html = (
        '<p>First &amp; best</p><p>Second<br/>line <a href="https://x.com">'
        '<span class="invisible">https://</span>x.com</a></p>'
    )
    assert html_text(html) == "First & best\n\nSecond\nline https://x.com"
    assert html_text("<p></p>") == ""


def test_an_id_too_big_for_a_bigint_is_not_a_status_id() -> None:
    assert parse_status_id(str(2**63 - 1)) == str(2**63 - 1)
    with pytest.raises(ValueError):
        parse_status_id("9" * 20)  # its time would be past the year 9999
