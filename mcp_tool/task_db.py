import sqlite3
from typing import List, Optional

class TaskDB:
    '''
    AI로 만든 코드
    Main Task가 있고 파생된(각각의 메서드) subTask
    '''
    def __init__(self, db_path=r"D:\dev\mcp\taskDB.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self):
        c = self.conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS MainTask (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS SubTask (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            main_task_id INTEGER,
            request TEXT,
            status TEXT,
            result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(main_task_id) REFERENCES MainTask(id)
        )""")
        self.conn.commit()

    def create_main_task(self, request: str) -> int:
        c = self.conn.cursor()
        c.execute("INSERT INTO MainTask(request, status) VALUES (?, ?)", (request, "pending"))
        self.conn.commit()
        return c.lastrowid

    def create_sub_tasks(self, main_task_id: int, functions: List[str]):
        c = self.conn.cursor()
        c.executemany("INSERT INTO SubTask(main_task_id, request, status) VALUES (?, ?, ?)",
                      [(main_task_id, fn, "pending") for fn in functions])
        self.conn.commit()

    def fetch_pending_sub_tasks(self):
        '''
        해결안된 모든 sub-task 를 가져온다.
        '''
        c = self.conn.cursor()
        c.execute("SELECT id, main_task_id, request FROM SubTask WHERE status='pending'")
        return [{"id": row[0], "main_task_id": row[1], "request": row[2]} for row in c.fetchall()]


    def fetch_pending_sub_tasks_by_main_id(self, main_task_id: int) -> List[dict]:
        '''
        해결안된 모든 sub-task 를 가져온다. (특정 main task 내에서)
        '''
        c = self.conn.cursor()
        c.execute("SELECT id, request FROM SubTask WHERE main_task_id=? AND status='pending'", (main_task_id,))
        return [{"id": row[0], "request": row[1]} for row in c.fetchall()]

    def update_sub_task(self, sub_task_id: int, result: str):
        '''
        task 상태 변경
        '''
        c = self.conn.cursor()
        c.execute("UPDATE SubTask SET status='done', result=? WHERE id=?", (result, sub_task_id))
        return self.conn.commit()



if __name__ == "__main__":
    taskDB = TaskDB()

    main_id = taskDB.create_main_task('Test Main Task')
    taskDB.create_sub_tasks(main_id, ['func1', 'func2', 'func3'])
    # TaskDB()

    # print(taskDB.fetch_pending_sub_tasks_by_main_id(2))
    print(taskDB.fetch_pending_sub_tasks()[13])