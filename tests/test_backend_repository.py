from datetime import UTC, datetime
from uuid import uuid4

from ares_backend.repository import (
    _notification_delivery_from_row,
    _profile_from_row,
    _push_device_from_row,
    _riot_account_from_row,
    _skin_watch_from_row,
)


def test_postgres_rows_are_normalized_for_pydantic_models() -> None:
    user_id = uuid4()
    now = datetime.now(UTC)

    profile = _profile_from_row(
        {
            "user_id": user_id,
            "display_name": "Cda",
            "avatar_url": "",
            "preferences": '{"theme":"dark"}',
        }
    )
    assert profile.user_id == str(user_id)
    assert profile.preferences == {"theme": "dark"}

    account = _riot_account_from_row(
        {
            "user_id": user_id,
            "puuid": "puuid",
            "game_name": "Player",
            "tag_line": "BR1",
            "region": "br",
            "shard": "na",
            "client_version": "release",
            "linked_at": now,
        }
    )
    assert account.user_id == str(user_id)

    device = _push_device_from_row(
        {
            "device_id": "device",
            "user_id": user_id,
            "push_token": "",
            "provider": "fcm",
            "masked_token": "ExponentPush...",
            "platform": "android",
            "device_name": "",
            "app_version": "",
            "enabled": True,
            "created_at": now,
            "updated_at": now,
        }
    )
    assert device.user_id == str(user_id)

    watch = _skin_watch_from_row(
        {
            "user_id": user_id,
            "item_id": "skin",
            "item_name": "Skin",
            "display_icon": "",
            "tier": "",
            "notify_enabled": True,
            "created_at": now,
            "updated_at": now,
        }
    )
    assert watch.user_id == str(user_id)

    delivery = _notification_delivery_from_row(
        {
            "delivery_key": "key",
            "user_id": user_id,
            "item_id": "skin",
            "item_name": "Skin",
            "source": "daily_store",
            "store_expires_at": None,
            "status": "sent",
            "ticket_ids": '["ticket"]',
            "error": "",
            "sent_at": now,
        }
    )
    assert delivery.user_id == str(user_id)
    assert delivery.ticket_ids == ["ticket"]
