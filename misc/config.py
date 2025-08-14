from pathlib import Path
from database import Database
from dotenv import load_dotenv

import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

TOKEN = os.getenv('BOT_TOKEN')
db_file = Path(BASE_DIR, "misc", 'db.sqlite')

BDB = Database(db_file)
