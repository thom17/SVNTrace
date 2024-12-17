from svn_oms.parser import SVNProjectParser
from svn_oms.db_handler import DBHandler
import time

def test_range_project(capsys):
    '''
    원래는 하나의 파일로 시작하려고 했는대
    결국 궁극적으로 프로젝트가 대상이어야 하니
    검색되는 리비전을 줄여서 프로젝트로 태스트 해나가는게 맞을듯
    '''

    print(test_range_project)
    path = r'D:\dev\AutoPlanning\trunk\AP_Auto_Task\mod_APImplantSimulation'
    start_rv = '7585'
    end_rv = '7587'
    #end는 head

    st_t = time.time()
    parser = SVNProjectParser(path=path, start_rv=start_rv, end_rv=end_rv)
    result = parser.parse()
    print(result)
    ed_t = time.time()
    print(ed_t-st_t)


    db = DBHandler()
    db.delete_all_nodes()

    st_t = time.time()
    parser.save_db(db)
    ed_t = time.time()
    print(ed_t-st_t)


def test_simple():
    datas = [d for d in range(2, 10)]
    print(datas)
    datas = [-999] + datas
    print(datas)