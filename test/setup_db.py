import sqlite3

def create_and_populate_db(db_path: str = "test.db") -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Drop the table if it already exists
    cur.execute("DROP TABLE IF EXISTS traffic_data;")

    # Create the traffic_data table
    cur.execute("""
    CREATE TABLE traffic_data (
        id INTEGER PRIMARY KEY,
        location TEXT,
        timestamp TEXT,
        count INTEGER
    );
    """)

    # Insert sample data
    rows = [
        ("Junction A", "2025-05-14 08:00:00", 120),
        ("Junction B", "2025-05-14 08:05:00", 85),
        ("Junction C", "2025-05-14 08:10:00", 95),
    ]
    cur.executemany(
        "INSERT INTO traffic_data (location, timestamp, count) VALUES (?, ?, ?)",
        rows
    )

    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_and_populate_db()
    print("Database 'test.db' created and populated with sample data.")