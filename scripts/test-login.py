#!/usr/bin/env python3
"""
Test login functionality for Bidar Auth Server.

Usage:
    BIDAR_TEST_PASSWORD='...' python scripts/test-login.py <username>

The password is read from BIDAR_TEST_PASSWORD or prompted for. It is never
taken from the command line, so it does not reach the shell history or the
process table.
"""

import asyncio
import getpass
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database import AsyncSessionLocal, engine
from src.crud.auth import (
    authenticate_user,
    create_access_token,
    get_password_hash,
    verify_password,
)
from src.crud.users import get_user_by_username


async def test_login(username: str, password: str) -> None:
    """Test login functionality."""
    print("=" * 70)
    print("🔐 Bidar Auth Server - Login Test")
    print("=" * 70)
    print()

    async with AsyncSessionLocal() as db:
        try:
            # 1. Check if user exists
            print(f"1️⃣  Checking if user '{username}' exists...")
            user = await get_user_by_username(db, username)

            if not user:
                print(f"❌ User '{username}' not found in database")
                return

            print(f"✅ User found:")
            print(f"   - ID: {user.id}")
            print(f"   - Username: {user.username}")
            print(f"   - Email: {user.email}")
            print(f"   - Role: {user.role}")
            print(f"   - Is Superuser: {user.is_superuser}")
            print(f"   - Is Active: {user.is_active}")
            print(f"   - Password Hash: {user.hashed_password[:7]}... (algorithm only)")
            print()

            # 2. Test password verification
            print("2️⃣  Testing password verification...")
            is_valid = verify_password(password, user.hashed_password)

            if is_valid:
                print("✅ Password verification successful!")
            else:
                print("❌ Password verification failed!")
                # Never print the password or the stored hash.
                test_hash = get_password_hash(password)
                print(
                    "   - Re-hashing the same password and verifying: "
                    f"{verify_password(password, test_hash)}"
                )
                return
            print()

            # 3. Test authentication
            print("3️⃣  Testing authentication...")
            auth_user = await authenticate_user(db, username, password)

            if not auth_user:
                print("❌ Authentication failed!")
                return

            print("✅ Authentication successful!")
            print()

            # 4. Test token creation
            print("4️⃣  Testing JWT token creation...")
            try:
                access_token = create_access_token(
                    data={
                        "sub": auth_user.username,
                        "user_id": auth_user.id,
                        "role": auth_user.role,
                    }
                )
                print("✅ Access token created successfully!")
                print(f"   Token (first 50 chars): {access_token[:50]}...")
            except Exception as e:
                print(f"❌ Token creation failed: {e}")
                return
            print()

            # 5. Summary
            print("=" * 70)
            print("✅ ALL TESTS PASSED!")
            print("=" * 70)
            print()
            print("Login credentials are valid:")
            print(f"  Username: {username}")
            print(f"  Password: ✓ (verified)")
            print(f"  Access Token: ✓ (generated)")
            print()
            print("If login still fails on the client, check:")
            print("  1. Network connectivity to the server")
            print("  2. CORS settings (ALLOWED_ORIGINS)")
            print("  3. Client-side token handling")
            print("  4. Server logs for actual error messages")

        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            import traceback

            traceback.print_exc()
        finally:
            await engine.dispose()


def main() -> None:
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/test-login.py <username>")
        print()
        print("Example:")
        print("  BIDAR_TEST_PASSWORD='...' python scripts/test-login.py bnbong")
        sys.exit(1)

    username = sys.argv[1]
    password = os.environ.get("BIDAR_TEST_PASSWORD") or getpass.getpass("Password: ")
    if not password:
        print("No password provided.")
        sys.exit(1)

    # Load environment variables
    from dotenv import load_dotenv

    env_file = Path(project_root) / ".env"

    if not env_file.exists():
        print("❌ Error: .env file not found")
        print(f"   Please create .env file at: {env_file}")
        sys.exit(1)

    load_dotenv(env_file)

    # Run test
    try:
        asyncio.run(test_login(username, password))
    except KeyboardInterrupt:
        print("\n❌ Test cancelled by user")
        sys.exit(1)


if __name__ == "__main__":
    main()
