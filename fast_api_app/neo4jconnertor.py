from typing import Optional
from neo4j_manager.neo4jHandler import Neo4jHandler

class Neo4jConnector:
    def __init__(self):
        self.uri = "bolt://localhost:7687"
        self.user = "neo4j"
        self.password = "123456789"
        self.database = "neo4j"

        self.db_map: dict[str, Neo4jHandler] = {}
        self.active_db: Optional[Neo4jHandler] = None
        self.login()

    def login(self):
        self.active_db = Neo4jHandler(uri=self.uri, user=self.user, password=self.password)
        for name in self.active_db.get_db_names():
            self.db_map[name] = Neo4jHandler(uri=self.uri, user=self.user, password=self.password, database=name)

    def show_databases(self):
        for name, db in self.db_map.items():
            if self.active_db == db:
                print(f"{name} (active)")
            else:
                print(f"{name}")
            db.print_info()
            print("node count : ", db.get_node_count())
            print("last modified : ", db.get_last_modified())



if __name__ == "__main__":
    connector = Neo4jConnector()
    connector.show_databases()