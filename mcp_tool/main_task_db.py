import sqlite3
from typing import List, Optional


class MainTaskDB:
    """
    MainTask 테이블 전용 클래스
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def init_schema(self):
        """MainTask 테이블 생성"""
        c = self.conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS MainTask (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        self.conn.commit()

    def create(self, request: str) -> int:
        """MainTask 생성"""
        c = self.conn.cursor()
        c.execute("INSERT INTO MainTask(request, status) VALUES (?, ?)", (request, "pending"))
        self.conn.commit()
        return c.lastrowid

    def get_all(self) -> List[dict]:
        """모든 MainTask 조회"""
        c = self.conn.cursor()
        c.execute("SELECT id, request, status, created_at FROM MainTask")
        return [
            {"id": row[0], "request": row[1], "status": row[2], "created_at": row[3]}
            for row in c.fetchall()
        ]

    def get_by_id(self, main_task_id: int) -> Optional[dict]:
        """특정 MainTask 조회"""
        c = self.conn.cursor()
        c.execute("SELECT id, request, status, created_at FROM MainTask WHERE id=?", (main_task_id,))
        row = c.fetchone()
        if row:
            return {"id": row[0], "request": row[1], "status": row[2], "created_at": row[3]}
        return None

    def update_status(self, main_task_id: int, status: str):
        """MainTask 상태 업데이트"""
        c = self.conn.cursor()
        c.execute("UPDATE MainTask SET status=? WHERE id=?", (status, main_task_id))
        self.conn.commit()

