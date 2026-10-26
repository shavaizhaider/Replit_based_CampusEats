from getpass import getpass
from pathlib import Path
import re
import sys

from dotenv import load_dotenv
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from app import create_app
from app.extensions import db
from app.models import Admin


def main() -> int:
    app = create_app()
    with app.app_context():
        db.create_all()
        if db.session.scalar(select(Admin.id).limit(1)):
            print("An administrator already exists. Use the admin sign-in page.")
            return 1
        username = input("Administrator username: ").strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]{3,80}", username):
            print("Use 3–80 letters, numbers, dots, underscores, or hyphens.")
            return 1
        password = getpass("Password (at least 12 characters): ")
        confirmation = getpass("Confirm password: ")
        if len(password) < 12:
            print("Password must be at least 12 characters.")
            return 1
        if password != confirmation:
            print("The passwords did not match.")
            return 1
        admin = Admin(username=username)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"Administrator {username} created.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
