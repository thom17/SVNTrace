'''
12-20
너무 복잡하다....
칼들고 나를 협박해서 아래의 과제를 수행하자.
0.먼저 end Rv로 프로젝트를 업데이트 그리고 strt_rv로 프로젝트를 업데이트한다.
이러면 base가 되는 파일들의 목록을 구할 수 있다.

그리고 근본이 strat_rv 이전이 더라도 start_rv의 데이터를 생산하자.
검색 범위 밖은 그냥 공백으로 처리하는게 맞는것 같다. (이문제는 추후에 다시 고려하자.)

1. CUnit을 생성하고 생성된 시점의 코드를 unit에 저장해두자. 
일단 이걸로 oms 생성을 위해 실제 파일을 동기화의 문제가 단순해진다. 또 너무 오래걸리지 않는듯. (하나의 파일 에대 max 8~10초 정도?)

2. SVNDataSet 에 기본적으로 파싱한 데이터를 다 때려 넣자.
모든 데이터 셋, 관계 데이터 셋 등 일단 이를 통해 중간 데이터도 DB화를 고려하자.
핵심적으로 db / parser의 입 출력으로 활용하자.

'''

import time

from typing import Union, List, Dict, Tuple, Set, Optional
from svn_manager.svn_data import Log, FileDiff, DiffActionType, LineChanges

import svn_manager.svn_data_factory as SVNFactory
import svn_manager.svn_manager as SVNManager
import oms.Mapper as OMS_Mapper
from oms.dataset.info_base import InfoSet,InfoBase

from clang.cindex import Cursor as CindexCursor

import clangParser.clang_utill as ClangUtill
from clangParser.CUnit import CUnit
from clangParser.Cursor import Cursor

from filemanager.FolderManager import FolderManager

from collections import defaultdict

from svn_oms.db_handler import DBHandler

from svn_oms.dataset.svn_trace_data import SVNTraceData, SVNTraceProjectData


def rv_to_int(revision: Union[str]) -> int:
    '''
    to do:
    사실 반드시 구현해야 할것같은대...
    '''

    return int(revision.replace('r', ''))

PathRevision = Tuple[str, str] #file_path, revision



class SVNProjectParser:
    def __init__(self, project_path: str, start_rv: Union[int, str] = None, end_rv :[Union, int] = 'HEAD'):
        self.project_path = project_path
        self.start_rv = start_rv
        self.end_rv = end_rv

        self.rv_log_diff: Dict[str, Tuple[Log, List[FileDiff]]] = {}
        self.trace_data_map:SVNTraceProjectData = SVNTraceProjectData(project_path=project_path, start_rv=start_rv, end_rv=end_rv)
    def __set_base_nodes(self):
        #마지막 리비전으로 이동. (탐색 범위 diff 정상 처리와 베이스 추적을 위해.)
        SVNManager.do_update(path=self.project_path, revision=self.end_rv)
        
        #log diff 초기화
        self.rv_log_diff = SVNManager.get_svn_range_log_dif(start_revision=self.start_rv, end_revision=self.end_rv, path=self.project_path)

        #시작 리비전으로 업데이트 하여 베이스 설정.
        update_files_dict = SVNManager.do_update(path=self.project_path, revision=self.start_rv)

        to_parse_files = []
        for mod, file_path_list in update_files_dict.items():
            if mod == 'A':
                self.trace_data_map.__delete_files = set(file_path_list)
                to_parse_files = to_parse_files + file_path_list

            elif mod == 'D':
                self.trace_data_map.__add_files = set(file_path_list)
            else:
                to_parse_files = to_parse_files + file_path_list

        #베이스 데이터 생성
        for file_path in to_parse_files:
            print(f'\rinit start rv({self.start_rv}) {file_path}\t\t', end='')
            self.trace_data_map.add_data(revision=self.start_rv, file_path=file_path)


    def parse(self):
        st = time.time()
        self.__set_base_nodes()


        for rv in sorted(self.rv_log_diff):
            if rv != self.start_rv:
                self.__update_step(revision=rv)
        ed = time.time()
        print(f'parse {ed-st:.2f} sec')


    def __update_step(self, revision: str):
        update_files_dict = SVNManager.do_update(path=self.project_path, revision=revision)

        log, diff_list= self.rv_log_diff[revision]
        for diff in diff_list:
            self.trace_data_map.update_data(diff)



