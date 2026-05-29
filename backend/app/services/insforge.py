import hmac
import hashlib
import time
import base64
import json
import sqlite3
from typing import Optional, List, Dict, Any
from loguru import logger

from app.core.database import get_db_connection

# A secure secret key for signing tokens
SECRET_KEY = "insforge-super-secret-key-k8s-agent"

def hash_password(password: str) -> str:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with a salt.
    """
    salt = os_salt = base64.b64encode(hashlib.sha256(password.encode()).digest()[:16]).decode()
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"{salt}:{base64.b64encode(key).decode()}"

def verify_password(password: str, password_hash: str) -> bool:
    """
    Verifies a password against its stored hash.
    """
    try:
        salt, stored_key = password_hash.split(':')
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        calculated_key = base64.b64encode(key).decode()
        return hmac.compare_digest(stored_key, calculated_key)
    except Exception as e:
        logger.error(f"Error verifying password: {str(e)}")
        return False

def generate_token(user_id: int, email: str, expiry_hours: int = 24) -> str:
    """
    Generates a secure HMAC-signed JWT-like token.
    """
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": time.time() + (expiry_hours * 3600)
    }
    payload_json = json.dumps(payload)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")
    
    # Generate signature
    signature = hmac.new(
        SECRET_KEY.encode(),
        payload_b64.encode(),
        hashlib.sha256
    ).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    
    return f"{payload_b64}.{signature_b64}"

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verifies a secure HMAC token and returns the parsed payload if valid.
    """
    try:
        if "." not in token:
            return None
            
        payload_b64, signature_b64 = token.split(".")
        
        # Verify signature
        expected_signature = hmac.new(
            SECRET_KEY.encode(),
            payload_b64.encode(),
            hashlib.sha256
        ).digest()
        expected_signature_b64 = base64.urlsafe_b64encode(expected_signature).decode().rstrip("=")
        
        if not hmac.compare_digest(signature_b64, expected_signature_b64):
            logger.warning("Token verification failed: Invalid signature.")
            return None
            
        # Decode and parse payload
        # Add padding back if necessary
        padding = 4 - (len(payload_b64) % 4)
        if padding < 4:
            payload_b64 += "=" * padding
            
        payload_json = base64.urlsafe_b64decode(payload_b64).decode()
        payload = json.loads(payload_json)
        
        # Check expiry
        if payload.get("exp", 0) < time.time():
            logger.warning("Token verification failed: Token expired.")
            return None
            
        return payload
    except Exception as e:
        logger.error(f"Error verifying token: {str(e)}")
        return None

def register_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Registers a new user in the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        password_hash = hash_password(password)
        cursor.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
        logger.info(f"Registered user: {email} with ID {user_id}")
        return {"id": user_id, "email": email}
    except sqlite3.IntegrityError:
        logger.warning(f"Registration failed: User {email} already exists.")
        return None
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return None
    finally:
        conn.close()

def login_user(email: str, password: str) -> Optional[str]:
    """
    Logs in a user and returns a token if successful.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        if not row:
            logger.warning(f"Login failed: User {email} not found.")
            return None
            
        user_id, email, password_hash = row["id"], row["email"], row["password_hash"]
        if verify_password(password, password_hash):
            token = generate_token(user_id, email)
            logger.info(f"Successful login for user: {email}")
            return token
        else:
            logger.warning(f"Login failed: Incorrect password for user {email}.")
            return None
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return None
    finally:
        conn.close()

def add_history_record(
    user_id: int,
    timestamp: str,
    root_cause: str,
    explanation: str,
    suggested_fix: str,
    command: str,
    namespace: str,
    confidence: int,
    status: str
) -> bool:
    """
    Saves an investigation log to the history table.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO history (
                timestamp, root_cause, explanation, suggested_fix, command, namespace, confidence, status, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (timestamp, root_cause, explanation, suggested_fix, command, namespace, confidence, status, user_id)
        )
        conn.commit()
        logger.info(f"Saved history record for user ID {user_id}: {root_cause}")
        return True
    except Exception as e:
        logger.error(f"Error adding history record: {str(e)}")
        return False
    finally:
        conn.close()

def get_history_records(user_id: int) -> List[Dict[str, Any]]:
    """
    Retrieves the list of investigations for a given user.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT timestamp, root_cause, explanation, suggested_fix, command, namespace, confidence, status FROM history WHERE user_id = ? ORDER BY id DESC",
            (user_id,)
        )
        rows = cursor.fetchall()
        records = []
        for r in rows:
            records.append({
                "timestamp": r["timestamp"],
                "root_cause": r["root_cause"],
                "explanation": r["explanation"],
                "suggested_fix": r["suggested_fix"],
                "command": r["command"],
                "namespace": r["namespace"],
                "confidence": r["confidence"],
                "status": r["status"]
            })
        return records
    except Exception as e:
        logger.error(f"Error getting history records: {str(e)}")
        return []
    finally:
        conn.close()
