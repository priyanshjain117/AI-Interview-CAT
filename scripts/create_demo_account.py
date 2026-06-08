#!/usr/bin/env python3
"""
PANELIQ — Demo Account Setup Script
====================================
Creates the demo@paneliq.local Supabase auth user and seeds all demo data.

Usage:
    cd /path/to/cat_interview
    python scripts/create_demo_account.py

Requirements:
    pip install supabase python-dotenv

Environment variables (loaded from .env automatically):
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    DEMO_USER_EMAIL     (default: demo@paneliq.local)
    DEMO_USER_PASSWORD  (default: demo1234)
    DEMO_USER_ID        (fixed UUID used in seed SQL)
"""

import os
import sys
from pathlib import Path

# Load .env from repo root
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

try:
    from supabase import create_client, Client
except ImportError:
    print("ERROR: supabase package not installed. Run: pip install supabase")
    sys.exit(1)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
DEMO_EMAIL = os.getenv("DEMO_USER_EMAIL", "demo@paneliq.local")
DEMO_PASSWORD = os.getenv("DEMO_USER_PASSWORD", "demo1234")
DEMO_USER_ID = os.getenv("DEMO_USER_ID", "c8122263-2008-4d34-a30c-4176b850e45c")

if not SUPABASE_URL or not SERVICE_KEY:
    print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
    sys.exit(1)

client: Client = create_client(SUPABASE_URL, SERVICE_KEY)


def create_demo_auth_user() -> str:
    """Create or confirm the demo auth user. Returns the user's UUID."""
    print(f"[1/3] Creating Supabase auth user: {DEMO_EMAIL}")
    try:
        # Try to create the user
        response = client.auth.admin.create_user({
            "email": DEMO_EMAIL,
            "password": DEMO_PASSWORD,
            "email_confirm": True,          # Skip email confirmation
            "user_metadata": {
                "full_name": "Demo Candidate",
            },
            "id": DEMO_USER_ID,             # Use the fixed UUID from seed SQL
        })
        uid = response.user.id
        print(f"    ✓ Created auth user with ID: {uid}")
        return uid
    except Exception as exc:
        msg = str(exc)
        if "already been registered" in msg or "already exists" in msg or "duplicate" in msg.lower():
            print(f"    ℹ  Auth user already exists — continuing with seed.")
            # Fetch existing user by email
            users = client.auth.admin.list_users()
            for u in users:
                if u.email == DEMO_EMAIL:
                    print(f"    ✓ Found existing user: {u.id}")
                    return u.id
            print("    WARNING: Could not find existing user. Continuing with fixed UUID.")
            return DEMO_USER_ID
        print(f"    ERROR: {exc}")
        raise


def run_seed_sql() -> None:
    """Execute the seed SQL file via Supabase DB."""
    seed_file = Path(__file__).resolve().parents[1] / "supabase" / "seed_demo_account.sql"
    if not seed_file.exists():
        print(f"ERROR: Seed file not found at {seed_file}")
        sys.exit(1)

    print(f"[2/3] Running seed SQL: {seed_file.name}")
    sql = seed_file.read_text()

    # Execute via Supabase RPC (requires the pgcrypto extension to be enabled)
    # We use the rpc endpoint with a raw SQL wrapper
    try:
        result = client.rpc("exec_sql", {"query": sql}).execute()
        print(f"    ✓ Seed SQL executed successfully")
    except Exception:
        # Fallback: try using postgrest raw if rpc doesn't work
        print("    ℹ  RPC exec_sql not available (expected) — please run seed SQL manually.")
        print(f"\n    Run this in the Supabase SQL Editor:")
        print(f"    → Supabase Dashboard → SQL Editor → paste contents of:")
        print(f"    → {seed_file}")
        return

    print("    ✓ Demo data seeded")


def verify_demo_data() -> None:
    """Verify that demo data is present in the DB."""
    print("[3/3] Verifying demo data")
    try:
        sessions = client.table("interview_sessions").select("id,status").eq("user_id", DEMO_USER_ID).execute()
        count = len(sessions.data or [])
        print(f"    ✓ Found {count} interview sessions for demo user")

        reports = client.table("reports").select("id,verdict,overall_score").eq("user_id", DEMO_USER_ID).execute()
        print(f"    ✓ Found {len(reports.data or [])} reports")

        for r in reports.data or []:
            print(f"      → Score: {r['overall_score']} | Verdict: {r['verdict']}")

        if count == 0:
            print("\n    ⚠  No sessions found. The seed SQL may need to be run manually.")
            print(f"    Run: supabase/seed_demo_account.sql in the Supabase SQL Editor")
    except Exception as exc:
        print(f"    ERROR during verification: {exc}")


if __name__ == "__main__":
    print("=" * 60)
    print("PANELIQ — Demo Account Setup")
    print("=" * 60)

    uid = create_demo_auth_user()
    run_seed_sql()
    verify_demo_data()

    print("\n" + "=" * 60)
    print("Setup complete!")
    print(f"  Demo email:    {DEMO_EMAIL}")
    print(f"  Demo password: {DEMO_PASSWORD}")
    print(f"  Demo user ID:  {uid}")
    print("\nIf seed SQL failed, run it manually in the Supabase SQL Editor.")
    print("=" * 60)
