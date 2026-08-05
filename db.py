import os
from sqlalchemy import create_engine

# Read database connection details from environment variables
HOST = os.getenv("DB_HOST")
PORT = os.getenv("DB_PORT", "5432")
DATABASE = os.getenv("supportdb")
USERNAME = os.getenv("DB_USER")
PASSWORD = os.getenv("DB_PASSWORD")

DATABASE_URL = (
    f"postgresql+psycopg2://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600
)
