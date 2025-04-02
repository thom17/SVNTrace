from neo4j_svntrace.maindb import MainDBManager


def test_run():
    print(test_run)
    db_manager = MainDBManager()
    db_manager.update_revision('8095')