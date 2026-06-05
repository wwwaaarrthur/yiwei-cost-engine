"""Shared database mode resolution for Yiwei Streamlit app and agents."""
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class DbConfig:
    path: str
    mode: str
    requested_mode: str
    source: str
    label: str
    description: str
    is_public: bool


def resolve_db_config(repo_root: str | None = None) -> DbConfig:
    """Resolve public/internal DB mode with fail-closed internal behavior.

    Modes:
    - YIWEI_APP_MODE=public: always use data/demo.db.
    - YIWEI_APP_MODE=internal: use YIWEI_DB_PATH or data/process_sheets.db; error if missing.
    - YIWEI_APP_MODE=auto/default: use YIWEI_DB_PATH, then local prod DB, then demo DB.
    """
    root = repo_root or os.path.dirname(os.path.abspath(__file__))
    prod = os.path.join(root, "data", "process_sheets.db")
    demo = os.path.join(root, "data", "demo.db")
    requested = os.getenv("YIWEI_APP_MODE", "auto").strip().lower() or "auto"
    custom = os.getenv("YIWEI_DB_PATH", "").strip()

    if requested not in {"auto", "public", "internal"}:
        raise ValueError(
            "Invalid YIWEI_APP_MODE. Use one of: auto, public, internal."
        )

    if requested == "public":
        return _checked_config(
            path=demo,
            mode="public",
            requested_mode=requested,
            source="data/demo.db",
            label="PUBLIC DEMO",
            description="Anonymized data for recruiters and GitHub viewers.",
            is_public=True,
        )

    if requested == "internal":
        path = custom or prod
        source = "YIWEI_DB_PATH" if custom else "data/process_sheets.db"
        return _checked_config(
            path=path,
            mode="internal",
            requested_mode=requested,
            source=source,
            label="INTERNAL",
            description="Real factory data for authenticated internal use.",
            is_public=False,
        )

    if custom:
        return _checked_config(
            path=custom,
            mode="internal",
            requested_mode=requested,
            source="YIWEI_DB_PATH",
            label="INTERNAL",
            description="Real factory data from YIWEI_DB_PATH.",
            is_public=False,
        )

    if os.path.exists(prod):
        return _checked_config(
            path=prod,
            mode="internal",
            requested_mode=requested,
            source="data/process_sheets.db",
            label="INTERNAL",
            description="Local production database detected.",
            is_public=False,
        )

    return _checked_config(
        path=demo,
        mode="public",
        requested_mode=requested,
        source="data/demo.db",
        label="PUBLIC DEMO",
        description="Anonymized fallback for public demo.",
        is_public=True,
    )


def _checked_config(
    path: str,
    mode: str,
    requested_mode: str,
    source: str,
    label: str,
    description: str,
    is_public: bool,
) -> DbConfig:
    if not os.path.exists(path):
        if mode == "internal":
            raise FileNotFoundError(
                "Internal mode requires a real database. Set YIWEI_DB_PATH or "
                "place process_sheets.db under data/. Refusing to fall back to demo data."
            )
        raise FileNotFoundError(
            "Public demo database not found. Ensure data/demo.db is committed."
        )

    return DbConfig(
        path=path,
        mode=mode,
        requested_mode=requested_mode,
        source=source,
        label=label,
        description=description,
        is_public=is_public,
    )
