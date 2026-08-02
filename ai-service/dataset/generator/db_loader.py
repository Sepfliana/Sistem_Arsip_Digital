import psycopg2

from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


class DatabaseLoader:
    def __init__(self):
        self.connection = None

    def connect(self):
        self.connection = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)

    def load_active_users(self):
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                SELECT u.id, u.username, r.nama_peran
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE u.is_active = TRUE
                  AND r.nama_peran IN ('Admin', 'Arsiparis', 'User')
                ORDER BY u.id
            """)
            return [{"user_id": row[0], "username": row[1], "role": row[2]} for row in cursor.fetchall()]
        finally:
            cursor.close()

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
