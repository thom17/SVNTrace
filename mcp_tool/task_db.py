import sqlite3
from typing import List, TYPE_CHECKING

from mcp_tool.main_task_db import MainTaskDB
from mcp_tool.sub_task_db import SubTaskDB

if TYPE_CHECKING:
    from svn_oms.dataset.svn_oms import RvFunctionInfo


class TaskDB:
    """
    MainTaskDB와 SubTaskDB를 조합하는 Facade 클래스
    DB 연결을 관리하고 하위 클래스들을 조합하여 제공
    """

    def __init__(self, db_path=r"D:\dev\mcp\taskDB.db"):
        self.conn = sqlite3.connect(db_path)
        self.main_task = MainTaskDB(self.conn)
        self.sub_task = SubTaskDB(self.conn)
        self._init_schema()

    def _init_schema(self):
        """테이블 스키마 초기화"""
        self.main_task.init_schema()
        self.sub_task.init_schema()

    # ==================== 하위 호환성을 위한 위임 메서드 ====================

    def create_main_task(self, request: str) -> int:
        """MainTask 생성 (하위 호환)"""
        return self.main_task.create(request)

    def create_sub_tasks(self, main_task_id: int, fn_codes: List[str]):
        """여러 SubTask 생성 (하위 호환)"""
        self.sub_task.create_batch(main_task_id, fn_codes)

    def create_sub_tasks_from_rv_infos(self, main_task_id: int, rv_infos: List['RvFunctionInfo']):
        """RvFunctionInfo 리스트로 SubTask 생성"""
        self.sub_task.create_batch_from_rv_infos(main_task_id, rv_infos)

    def fetch_pending_sub_tasks(self) -> List[dict]:
        """해결 안된 모든 SubTask 조회 (하위 호환)"""
        return self.sub_task.fetch_pending()

    def fetch_pending_sub_tasks_by_main_id(self, main_task_id: int) -> List[dict]:
        """특정 MainTask의 미해결 SubTask 조회 (하위 호환)"""
        return self.sub_task.fetch_pending_by_main_id(main_task_id)

    def get_all_sub_tasks(self) -> List[dict]:
        """모든 SubTask 조회 (하위 호환)"""
        return self.sub_task.get_all()

    def get_all_main_tasks(self) -> List[dict]:
        """모든 MainTask 조회 (하위 호환)"""
        return self.main_task.get_all()

    def update_sub_task(self, sub_task_id: int, result: str):
        """SubTask 상태 변경 (하위 호환)"""
        self.sub_task.update(sub_task_id, result)

    def close(self):
        """DB 연결 종료"""
        self.conn.close()


if __name__ == "__main__":
    # 테스트용 새 DB 사용
    taskDB = TaskDB(db_path=r"D:\dev\mcp\taskDB_v2.db")

    # 기존 방식 (하위 호환)
    main_id = taskDB.create_main_task('Test Main Task')
    taskDB.create_sub_tasks(main_id, ['func1', 'func2', 'func3'])

    # 새로운 방식 (직접 접근)
    main_id2 = taskDB.main_task.create('Another Task via direct access')
    taskDB.sub_task.create_batch(main_id2, ['code1', 'code2'])

    print("All Main Tasks:", taskDB.get_all_main_tasks())
    print("All Sub Tasks:", taskDB.get_all_sub_tasks())
