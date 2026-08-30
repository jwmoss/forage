"""Tests for Facebook Marketplace search support."""

from unittest.mock import MagicMock

from forage.parser import parse_marketplace_listing
from forage.scraper import _marketplace_listing_within_radius, get_marketplace_url


def test_parse_marketplace_listing() -> None:
    element = MagicMock()
    element.get_attribute.return_value = (
        "/marketplace/item/1618126739675766/?ref=search"
    )
    element.inner_text.return_value = (
        "Just listed\n$400\nNVIDIA RTX 4070 Super\nWilmington, NC"
    )

    listing = parse_marketplace_listing(element)

    assert listing is not None
    assert listing.model_dump() == {
        "id": "1618126739675766",
        "url": "https://www.facebook.com/marketplace/item/1618126739675766/",
        "title": "NVIDIA RTX 4070 Super",
        "price": "$400",
        "location": "Wilmington, NC",
    }


def test_get_marketplace_url() -> None:
    url = get_marketplace_url("rtx 4070", "wilmington", 40)

    assert url == (
        "https://www.facebook.com/marketplace/wilmington/search/"
        "?query=rtx+4070&radius=40&sortBy=creation_time_descend&category=electronics"
    )


def test_marketplace_listing_within_radius() -> None:
    center = (34.1327051, -77.9210288)
    item_id = "1618126739675766"
    detail_html = (
        f'"id":"{item_id}","location":{{"latitude":33.780212402344,'
        '"longitude":-78.975219726562}'
    )
    local_detail_html = (
        '"location":{"latitude":34.197692871094,"longitude":-77.887573242188},'
        f'"id":"{item_id}"'
    )

    assert not _marketplace_listing_within_radius(detail_html, center, 40)
    assert _marketplace_listing_within_radius(local_detail_html, center, 40)
