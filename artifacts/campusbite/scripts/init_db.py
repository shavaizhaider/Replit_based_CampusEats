from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    db.create_all()
    print("CampusBite database tables are ready.")
