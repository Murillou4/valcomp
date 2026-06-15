from ares_backend.store import (
    VP_CURRENCY_ID,
    extract_daily_offer_ids,
    extract_night_market_offer_ids,
    extract_prices,
    inventory_item_ids,
)


def test_normalizes_daily_storefront_v2_layout() -> None:
    raw = {
        "SkinsPanelLayout": {
            "SingleItemOffers": ["skin-a", "skin-b"],
            "SingleItemOffersRemainingDurationInSeconds": 3600,
        },
        "Offers": [
            {"OfferID": "skin-a", "Cost": {VP_CURRENCY_ID: 1775}},
            {"OfferID": "skin-b", "Cost": {VP_CURRENCY_ID: 875}},
        ],
    }

    ids, seconds = extract_daily_offer_ids(raw)

    assert ids == ["skin-a", "skin-b"]
    assert seconds == 3600
    assert extract_prices(raw) == {"skin-a": 1775, "skin-b": 875}


def test_normalizes_nested_v3_storefront_shape() -> None:
    raw = {
        "Store": {
            "SkinsPanelLayout": {
                "SingleItemOffers": [{"Rewards": [{"ItemID": "skin-c"}]}],
                "SingleItemOffersRemainingDurationInSeconds": 120,
            },
            "StoreOffers": [{"Rewards": [{"ItemID": "skin-c"}], "Cost": {VP_CURRENCY_ID: 2175}}],
        }
    }

    ids, seconds = extract_daily_offer_ids(raw)

    assert ids == ["skin-c"]
    assert seconds == 120
    assert extract_prices(raw)["skin-c"] == 2175


def test_extracts_night_market_and_inventory_ids() -> None:
    raw = {
        "BonusStore": {
            "BonusStoreOffers": [
                {
                    "Offer": {"Rewards": [{"ItemID": "skin-night"}]},
                    "DiscountCosts": {VP_CURRENCY_ID: 1000},
                }
            ]
        }
    }
    inventory = {
        "EntitlementsByTypes": [
            {"Entitlements": [{"ItemID": "skin-owned"}, {"ItemID": "skin-night"}]}
        ]
    }

    assert extract_night_market_offer_ids(raw) == ["skin-night"]
    assert extract_prices(raw)["skin-night"] == 1000
    assert inventory_item_ids(inventory) == {"skin-owned", "skin-night"}

