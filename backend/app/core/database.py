import sqlite3
import os
from loguru import logger

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "insforge.db")

def get_db_connection() -> sqlite3.Connection:
    """
    Returns a connection to the SQLite database.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initializes the database directory and tables if they do not exist.
    """
    # Create data directory if it doesn't exist
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        logger.info(f"Created database directory at {DB_DIR}")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
        """)

        # Create history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                root_cause TEXT NOT NULL,
                explanation TEXT NOT NULL,
                suggested_fix TEXT NOT NULL,
                command TEXT NOT NULL,
                namespace TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                status TEXT NOT NULL,
                user_id INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
        """)

        conn.commit()
        logger.info("InsForge database successfully initialized.")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise e
    finally:
        conn.close()
