from neo4j_svntrace.maindb import TraceDataBase
from clangParser.clangParser import find_cpp_files

from svn_managers.svn_data import Log
import svn_managers.svn_manager as SVNManager
import oms.Mapper as OMSMapper

import svn_oms.dataset.rv_info_factory as RVInfoFactory




def update_trace(db: TraceDataBase):
    head_rv = db.get_head_revision()
    local_rv = SVNManager.get_current_revision(db.local_path)
    if head_rv is None:
        head_rv = local_rv
    repo_rv = SVNManager.get_head_revision(db.repo_path)

    # head rv는 update 되지 않고 local 만 update 처리 된경우
    if int(head_rv) < int(local_rv):
        rv = int(head_rv)  # head rv 부터 시작
    else:
        rv = int(local_rv)

    # 먼저 로컬 파일 업데이트 및 파싱
    while rv <= int(repo_rv):
        db.update_revision(rv)
        rv += 1

    # 모든 리비전 업데이트 후 관계 재설정
    db.reconnect_trace_relationship()
    # 마지막으로 head 노드 갱신
    db.connect_head_info()


def init_head_nodes(db: TraceDataBase, skip_keywords: list[str]=[]):
    local_path = db.get_local_path()
    all_file_paths = set(find_cpp_files(local_path))
    file_paths = []
    skip_list = []
    for path in all_file_paths:
        if not any(skip in path for skip in skip_keywords):
            file_paths.append(path)
        else:
            skip_list.append(path)

    print('타겟 파일 수: ', len(file_paths) , 'skip ', len(skip_list), '총합 :', len(all_file_paths))

    li = db.get_latest_rv_units_per_path()
    print('db에 저장된 Head RVUnit 수: ', len(li))
    for node in li:
        file_path = node['file_path']
        if file_path in file_paths:
            file_paths.remove(file_path)
        else:
            print(file_path)
            rv = SVNManager.get_current_revision(file_path)
            print(rv)
            assert f'db head 에는 있으나 실제 파일은 없음 ({file_path}'

    print('추가할 총 파일 수 : ', len(file_paths))

    to_save_datas = []
    to_save_relationships = []
    progress = 0
    for file_path in file_paths:
        percent = (100 * progress) / len(file_paths)
        print(f'\r{percent:.2f}% 파싱중: {file_path} (to save {len(to_save_datas)} / {len(to_save_relationships)})', end='\t\t')
        head = Log.from_subprocess_by_path(file_path)[0]
        rv_unit, rv_info_list = RVInfoFactory.from_parsing(head.revision, file_path)

        to_save_datas.extend([rv_unit] + rv_info_list)
        to_save_relationships.extend( [(rv_unit, info, 'has') for info in rv_info_list] )
        progress += 1

        if 1000 < len(to_save_datas):
            print(f'\n부분 저장 중... to save {len(to_save_datas)} / {len(to_save_relationships)}')
            db.neo4j.save_data(to_save_datas)
            db.neo4j.add_relationship(to_save_relationships)
            to_save_datas = []
            to_save_relationships = []


    db.neo4j.save_data(to_save_datas)
    db.neo4j.add_relationship(to_save_relationships)


    # for file_paths in file_paths:







if __name__ == "__main__":
    print()

    db = TraceDataBase(database='test1106')
    # db.update_file_path_normalize()
    init_head_nodes(db,  ['libs', 'external_'])
    db.reconnect_trace_relationship()
    db.connect_head_info()
