import sqlite3
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from svn_oms.dataset.svn_oms import RvFunctionInfo


class SubTaskDB:
    """
    SubTask 테이블 전용 클래스
    RvFunctionInfo와 대응되는 속성들을 포함
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def init_schema(self):
        """SubTask 테이블 생성 (RvFunctionInfo 속성 포함)"""
        c = self.conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS SubTask (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            main_task_id INTEGER,
            src_name TEXT,
            file_path TEXT,
            revision TEXT,
            rv_src TEXT,
            code TEXT,
            status TEXT,
            result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(main_task_id) REFERENCES MainTask(id)
        )""")
        self.conn.commit()

    # ==================== Create ====================

    def create(self, main_task_id: int, code: str) -> int:
        """기본 SubTask 생성 (code만)"""
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO SubTask(main_task_id, code, status) VALUES (?, ?, ?)",
            (main_task_id, code, "pending")
        )
        self.conn.commit()
        return c.lastrowid

    def create_batch(self, main_task_id: int, codes: List[str]):
        """여러 SubTask 일괄 생성 (code만)"""
        c = self.conn.cursor()
        c.executemany(
            "INSERT INTO SubTask(main_task_id, code, status) VALUES (?, ?, ?)",
            [(main_task_id, code, "pending") for code in codes]
        )
        self.conn.commit()

    def create_from_rv_info(self, main_task_id: int, rv_info: 'RvFunctionInfo') -> int:
        """RvFunctionInfo 객체로부터 SubTask 생성"""
        c = self.conn.cursor()
        c.execute("""
            INSERT INTO SubTask(main_task_id, src_name, file_path, revision, rv_src, code, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            main_task_id,
            rv_info.info_base.src_name,
            rv_info.info_base.file_path,
            rv_info.revision,
            rv_info.rv_src,
            rv_info.info_base.code,
            "pending"
        ))
        self.conn.commit()
        return c.lastrowid

    def create_batch_from_rv_infos(self, main_task_id: int, rv_infos: List['RvFunctionInfo']):
        """여러 RvFunctionInfo 객체로부터 SubTask 일괄 생성"""
        c = self.conn.cursor()
        c.executemany("""
            INSERT INTO SubTask(main_task_id, src_name, file_path, revision, rv_src, code, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                main_task_id,
                rv_info.info_base.src_name,
                rv_info.info_base.file_path,
                rv_info.revision,
                rv_info.rv_src,
                rv_info.info_base.code,
                "pending"
            ) for rv_info in rv_infos
        ])
        self.conn.commit()

    # ==================== Read ====================

    def fetch_pending(self) -> List[dict]:
        """해결 안된 모든 SubTask 조회"""
        c = self.conn.cursor()
        c.execute("""
            SELECT id, main_task_id, src_name, file_path, revision, rv_src, code 
            FROM SubTask WHERE status='pending'
        """)
        return [
            {
                "id": row[0],
                "main_task_id": row[1],
                "src_name": row[2],
                "file_path": row[3],
                "revision": row[4],
                "rv_src": row[5],
                "code": row[6]
            }
            for row in c.fetchall()
        ]

    def fetch_pending_by_main_id(self, main_task_id: int) -> List[dict]:
        """특정 MainTask의 미해결 SubTask 조회"""
        c = self.conn.cursor()
        c.execute("""
            SELECT id, src_name, file_path, revision, rv_src, code 
            FROM SubTask WHERE main_task_id=? AND status='pending'
        """, (main_task_id,))
        return [
            {
                "id": row[0],
                "src_name": row[1],
                "file_path": row[2],
                "revision": row[3],
                "rv_src": row[4],
                "code": row[5]
            }
            for row in c.fetchall()
        ]

    def get_all(self) -> List[dict]:
        """모든 SubTask 조회"""
        c = self.conn.cursor()
        c.execute("""
            SELECT id, main_task_id, src_name, file_path, revision, rv_src, code, status, result 
            FROM SubTask
        """)
        return [
            {
                "id": row[0],
                "main_task_id": row[1],
                "src_name": row[2],
                "file_path": row[3],
                "revision": row[4],
                "rv_src": row[5],
                "code": row[6],
                "status": row[7],
                "result": row[8]
            }
            for row in c.fetchall()
        ]

    def get_by_id(self, sub_task_id: int) -> Optional[dict]:
        """특정 SubTask 조회"""
        c = self.conn.cursor()
        c.execute("""
            SELECT id, main_task_id, src_name, file_path, revision, rv_src, code, status, result 
            FROM SubTask WHERE id=?
        """, (sub_task_id,))
        row = c.fetchone()
        if row:
            return {
                "id": row[0],
                "main_task_id": row[1],
                "src_name": row[2],
                "file_path": row[3],
                "revision": row[4],
                "rv_src": row[5],
                "code": row[6],
                "status": row[7],
                "result": row[8]
            }
        return None

    # ==================== Update ====================

    def update(self, sub_task_id: int, result: str):
        """SubTask 상태를 'done'으로 변경하고 결과 저장"""
        c = self.conn.cursor()
        c.execute(
            "UPDATE SubTask SET status='done', result=? WHERE id=?",
            (result, sub_task_id)
        )
        self.conn.commit()

    def count_pending_by_main_id(self, main_task_id: int) -> int:
        """특정 MainTask의 미해결 SubTask 개수"""
        c = self.conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM SubTask WHERE main_task_id=? AND status='pending'",
            (main_task_id,)
        )
        return c.fetchone()[0]

