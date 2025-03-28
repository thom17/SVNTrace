# import svn_manager.svn_manager as SVNManager
#
file_path = r'D:\dev\AutoPlanning\trunk\AP_trunk_pure\mod_APWorkSpace\UIDlgWorklistMain.cpp'
rv = 7631
# dif_map = SVNManager.get_diif_map(path=file_path, revision=rv)
#
# code = SVNManager.get_file_at_revision(file_path=file_path, revision=rv)
#
# print(dif_map)
# print(code)
# print()

import svn_manager.svn_manager as SVNManager

from svn_oms.db_handler import DBHandler
from clangParser.CUnit import CUnit

from svn_manager.svn_data import Log
import oms.Mapper as Mapper

def get_test_oms():
    file_path = r'D:\dev\AutoPlanning\trunk\AP_trunk_pure\mod_APImplantSimulation\UIDlgImplantLib.cpp'
    base_unit = CUnit.parse(file_path)
    node = base_unit.get_in_range_node(2222)
    infos, _ = Mapper.parsing([node])
    print(infos)

    info_list = []
    for info in infos.functionInfos.values():
        info_list.append(info)
    return info_list

def test_get_rv_oms_pair():
    info_list = get_test_oms()

    db_handel =DBHandler()
    db_handel.neo4j.delete_all_nodes()

    db_handel.save_data(info_list, revision=0)
    db_handel.print_info()

    db_handel.save_data(info_list, revision=10)
    db_handel.print_info()

    #바로 집어넣으면 두개 검색되니.?
    db_handel.add_relationship([(info_list[0], info_list[1], '0->10')])


def test_one_file_trace():
    '''
    일단 하나의 파일에 대해서 전체적인 파싱 처리
    :return: 
    '''

    target_file = r'D:\dev\AutoPlanning\trunk\AP_trunk_pure\AppUICore\ActuatorHybrid.cpp'

    #업데이트로 최신화
    SVNManager.do_update(target_file)

    db_handel =DBHandler()
    db_handel.neo4j.delete_all_nodes()

    logs = Log.from_subprocess_by_path(target_file)
    rvs = [log.revision for log in logs]
    pos = len(rvs)-2
    while 0<pos:
        rv = int(rvs[pos])
        print(f'\r{len(rvs) - pos} / {len(rvs)} pos / rv = {pos} / {rv}', end='\t\t')
        if 5000 < rv:
            to_save(rv=rv, file_path=target_file, db_handel=db_handel)
        pos -= 1



def to_save(rv, file_path, db_handel):
    '''
    test_all_in_one 메서드화
    '''
    # r = Main.get_rv_oms_pair(revision=rv, file_path=file_path)

    del_infos, add_infos = OMSGetter.get_rv_oms_pair(revision=rv, file_path=file_path)
    before_rv = SVNManager.get_before_change_rv(path=file_path, revision=rv)


    src_di = {}
    for info in del_infos:
        src_di[info.src_name] = [info]


    for info in add_infos:
        if info.src_name in src_di:
            src_di[info.src_name].append(info)
        else:
            src_di[info.src_name] = [None, info]

    #각각 저장
    db_handel.save_data(data_list=del_infos, revision=before_rv)
    db_handel.save_data(data_list=add_infos, revision=rv)


    node_map = db_handel.neo4j.get_nodes_map()
    ref_list = []
    for infos in  src_di.values():
        if len(infos) == 2:
            info1, info2 = infos
            if  info1 and info2:
                ref_list.append((info1, info2, 'update'))

    db_handel.add_relationship(ref_list)



def test_all_in_one():
    # r = Main.get_rv_oms_pair(revision=rv, file_path=file_path)
    del_infos, add_infos = OMSGetter.get_rv_oms_pair(revision=rv, file_path=file_path)
    before_rv = SVNManager.get_before_change_rv(path=file_path, revision=rv)


    print([info.src_name for info in del_infos])
    print([info.src_name for info in add_infos])

    before_src = [info.src_name for info in del_infos]
    src_di = {}
    for info in del_infos:
        src_di[info.src_name] = [info]


    for info in add_infos:
        if info.src_name in src_di:
            src_di[info.src_name].append(info)
        else:
            src_di[info.src_name] = [None, info]

    # print(del_infos[0].code)
    # print(add_infos[0].code)

    db_handel =DBHandler()
    db_handel.neo4j.delete_all_nodes()

    #각각 저장
    db_handel.save_data(data_list=del_infos, revision=before_rv)
    db_handel.save_data(data_list=add_infos, revision=rv)
    db_handel.neo4j.print_info()

    node_map = db_handel.neo4j.get_nodes_map()
    ref_list = []
    for info1, info2 in  src_di.values():
        if info1 and info2:
            ref_list.append((info1, info2, 'update'))

    db_handel.add_relationship(ref_list)
    db_handel.neo4j.print_info()

    print(node_map)

    # for infos in src_di.values():
    #     if None in infos:
    #         continue
    #     else:
    #         db_handel.neo4j.



# def save_db_pair():

