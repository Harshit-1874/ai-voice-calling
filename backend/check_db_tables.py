#!/usr/bin/env python3

import sqlite3
import os

# Database path
db_path = 'prisma/voice_calling.db'

if not os.path.exists(db_path):
    print(f"Database file not found: {db_path}")
    exit(1)

# Connect to SQLite database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("=== Database Tables ===")
for table in tables:
    print(f"  - {table[0]}")

# Check transcriptions table structure
print("\n=== Transcriptions Table Structure ===")
try:
    cursor.execute("PRAGMA table_info(transcriptions)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
except Exception as e:
    print(f"Error checking transcriptions table: {e}")

# Check if transcriptions table has any data
print("\n=== Transcriptions Data ===")
try:
    cursor.execute("SELECT COUNT(*) FROM transcriptions")
    count = cursor.fetchone()[0]
    print(f"Total transcriptions: {count}")
    
    if count > 0:
        cursor.execute("SELECT * FROM transcriptions LIMIT 5")
        rows = cursor.fetchall()
        print("Sample transcriptions:")
        for row in rows:
            print(f"  - {row}")
except Exception as e:
    print(f"Error checking transcriptions data: {e}")

# Check call_logs table
print("\n=== Call Logs Data ===")
try:
    cursor.execute("SELECT COUNT(*) FROM call_logs")
    count = cursor.fetchone()[0]
    print(f"Total call logs: {count}")
    
    if count > 0:
        cursor.execute("SELECT callSid, status, startTime FROM call_logs ORDER BY startTime DESC LIMIT 5")
        rows = cursor.fetchall()
        print("Recent call logs:")
        for row in rows:
            print(f"  - {row[0]} | {row[1]} | {row[2]}")
except Exception as e:
    print(f"Error checking call logs: {e}")

conn.close()
