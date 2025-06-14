import sqlite3
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self):
        self.db_path = "contacts.db"
    
    async def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    async def add_contact(self, name: str, phone: str) -> Dict:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO contacts (name, phone) VALUES (?, ?)",
                (name, phone)
            )
            conn.commit()
            contact_id = cursor.lastrowid
            conn.close()
            return {"id": contact_id, "name": name, "phone": phone}
        except sqlite3.IntegrityError:
            raise ValueError("Phone number already exists")
        except Exception as e:
            logger.error(f"Error adding contact: {str(e)}")
            raise
    
    async def get_contact(self, phone: str) -> Optional[Dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, phone FROM contacts WHERE phone = ?",
                (phone,)
            )
            result = cursor.fetchone()
            conn.close()
            if result:
                return {"id": result[0], "name": result[1], "phone": result[2]}
            return None
        except Exception as e:
            logger.error(f"Error getting contact: {str(e)}")
            raise
    
    async def get_all_contacts(self) -> List[Dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, phone FROM contacts")
            results = cursor.fetchall()
            conn.close()
            return [
                {"id": row[0], "name": row[1], "phone": row[2]}
                for row in results
            ]
        except Exception as e:
            logger.error(f"Error getting all contacts: {str(e)}")
            raise
    
    async def update_contact(self, phone: str, name: str) -> Dict:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE contacts SET name = ? WHERE phone = ?",
                (name, phone)
            )
            conn.commit()
            conn.close()
            return {"name": name, "phone": phone}
        except Exception as e:
            logger.error(f"Error updating contact: {str(e)}")
            raise
    
    async def delete_contact(self, phone: str) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM contacts WHERE phone = ?", (phone,))
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except Exception as e:
            logger.error(f"Error deleting contact: {str(e)}")
            raise 