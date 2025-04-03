from neo4j_svntrace.maindb import MainDBManager
import os
def os_path_check(path1, path2):
    return os.path.normpath(path1) == os.path.normpath(path2)

# def test_run():
#     print(test_run)
#     db_manager = MainDBManager()
#     db_manager.update_revision('8100')
#     # for rv in range(7000, 8100):
#     #     db_manager.update_revision('')

# def test_main():
#     db = MainDBManager()
#     # db.neo4j.delete_all_nodes()
#
#     for i in range(100):
#         print('update : ', i+8000)
#         db.update_revision(str(i+8000))
#
#     db.update_trace()
#
# def test_print_info():
#     db_manager = MainDBManager()
#     db_manager.neo4j.print_info()

def test_update_trace():
    print(test_update_trace)

    db_manager = MainDBManager()

    db_manager.update_trace()



# from py2neo import Node, Relationship
# def test_node():
#     print(test_node)
#     db_manager = MainDBManager()
#     neo4j = db_manager.neo4j
#
#     log:Node = list(neo4j.graph.nodes.match('Log', revision='8077'))[0]
#     print(log)
#
#     target_path = r'D:\dev\AutoPlanning\trunk\AP_trunk_pure\mod_APSurgicalGuide\ToolBarSurgicalGuide.cpp'
#     file_diffs:Node = list(neo4j.graph.nodes.match('FileDiff', revision='8077'))
#     for file_diff in file_diffs:
#         if file_diff['filepath'] == target_path:
#             print('find')
#         if os_path_check(file_diff['filepath'], target_path):
#             print('find with os_path_check')
#
#     file_diff:Node = list(neo4j.graph.nodes.match('FileDiff', revision='8077', filepath=target_path))[0]
#
#     rv_unit = db_manager.get_rv_node_by_path('RvUnit' ,file_diff['revision'], file_diff['filepath'])
#     print(rv_unit)
#
#     rels: Relationship = list(neo4j.graph.match((rv_unit, None), r_type='has'))
#     print('rels : ' , len(rels))
#     rel = rels[0]
#     check = (rel.start_node == rv_unit)
#
#     print('rel type' ,type(rel))
#     print('start node : ' , rel.start_node == log)
#     print('end node : ' , rel.end_node == file_diff)
#
#     print('filepath = ' , file_diff['filepath'] )
#     print('repo = ' , file_diff['repo_path'] )
#
#
#
#     print(file_diff)
#
#     print(type(log))
#     print(log['revision'])
#     # log
#     print(type(log.relationships))
#
#
#
# def test_update_path():
#     print(test_update_path)
#     db_manager = MainDBManager()
#     db_manager.update_file_path_normalize()