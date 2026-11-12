"""Optional Supabase persistence adapter. Without credentials, the app uses session state + export."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any


def _supabase_client(url: str, key: str):
    try:
        from supabase import create_client
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Paket supabase belum terpasang.") from exc
    return create_client(url, key)


def is_configured(url: str | None, key: str | None) -> bool:
    return bool(url and key)


def save_snapshot(url: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
    client = _supabase_client(url, key)
    row = {
        "project_name": str(payload.get("property", {}).get("name", "Analisis tanpa nama")),
        "status": str(payload.get("decision", {}).get("status", "HOLD")),
        "analysis_date": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    response = client.table("analyses").insert(row).execute()
    return response.data[0] if getattr(response, "data", None) else row


def list_snapshots(url: str, key: str, limit: int = 100) -> list[dict[str, Any]]:
    client = _supabase_client(url, key)
    response = client.table("analyses").select("id, project_name, status, analysis_date, payload").order("analysis_date", desc=True).limit(limit).execute()
    return list(getattr(response, "data", []) or [])
