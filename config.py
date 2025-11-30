from dotenv import load_dotenv
import os

load_dotenv()

ADMIN_IDS=list(map(int, os.getenv("ADMIN_IDS", "").split(",")))