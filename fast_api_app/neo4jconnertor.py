from typing import Optional
from neo4j_svntrace.maindb import TraceDataBase  # MainDBManager 사용

class Neo4jConnector:
    def __init__(self):
        self.uri = "bolt://localhost:7687"
        self.user = "neo4j"
        self.password = "123456789"
        self.database = "neo4j"

        # self.db_map: dict[str, Neo4jHandler] = {}
        # self.active_db: Optional[Neo4jHandler] = None
        self.db_map: dict[str, TraceDataBase] = {}
        self.active_db: Optional[TraceDataBase] = None
        self.login()

    def login(self):
        # self.active_db = Neo4jHandler(uri=self.uri, user=self.user, password=self.password)
        # for name in self.active_db.get_db_names():
        #     self.db_map[name] = Neo4jHandler(uri=self.uri, user=self.user, password=self.password, database=name)
        self.active_db = TraceDataBase(uri=self.uri, user=self.user, password=self.password, database=self.database)
        self.db_map.clear()
        for name in self.active_db.get_db_names():
            self.db_map[name] = TraceDataBase(uri=self.uri, user=self.user, password=self.password, database=name)

    def show_databases(self):
        for name, db in self.db_map.items():
            if self.active_db == db:
                print(f"{name} (active)")
            else:
                print(f"{name}")
            db.print_info()
            print("node count : ", db.get_node_count())
            print("last modified : ", db.get_last_modified())
            print("head revision : ", db.get_head_revision())
            print("local revision : ", db.get_local_revision())
            print("repo revision : ", db.get_repo_revision())
            print("local path : ", db.get_local_path())  # 선택사항: 콘솔 출력


if __name__ == "__main__":
    connector = Neo4jConnector()
    connector.show_databases()