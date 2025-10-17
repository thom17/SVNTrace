from neo4j_svntrace.maindb import TraceDataBase
import os

# def test_run():
#     print(test_run)
#     db_manager = MainDBManager()
#     db_manager.update_revision('8100')
#     # for rv in range(7000, 8100):
#     #     db_manager.update_revision('')


#기존태스트
# db = TraceDataBase()
# # db.neo4j.delete_all_nodes()
#
# # db.reconnect_trace_relationship()
#
#
# start_rv =8000
# size = 1000
# for i in range(size):
#     print('update : ', i+start_rv)
#     db.update_revision(str(i+start_rv))
#
# print('update done')
# # db.update_trace()
#
# db.reconnect_trace_relationship()
# db.connect_head_info()


#2025-10-17 update trace 수정
db = TraceDataBase()
db.update_trace()
