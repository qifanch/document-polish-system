from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import create_user


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a local login user.")
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("--display-name", default="")
    args = parser.parse_args()

    user = create_user(args.username, args.password, args.display_name or args.username)
    print(f"created user: {user['username']} ({user['displayName']})")


if __name__ == "__main__":
    main()
