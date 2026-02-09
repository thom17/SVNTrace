'''
일단 이것도 Neo4j에 저장. (디버깅 용도)

'''
from importlib.resources import read_text
from typing import Optional, List, Dict, Union, Tuple, Set
import os
from dataclasses import dataclass

from clangParser.datas.CUnit import CUnit
import clangParser.clang_utill as ClangUtill
import clang.cindex as ClangIndex

import svn_manager.svn_manager as SVNManager
from svn_manager.svn_data import FileDiff, LineChanges ,DiffActionType

PathStr = str
Revision = Union[str, int]

RvPath = Tuple[Revision, PathStr]

class SVNTraceData:
    """
    그래프의 노드 역활
    """
    def __init__(self, revision: Revision, file_path: PathStr, unit: Optional[CUnit], is_none:bool = False):
        #두가지는 필수. 사실상 ID
        self.revision: PathStr = revision
        self.file_path: Revision = file_path

        self.repo_path: str = SVNManager.get_repo_url(path=file_path)

        self.unit: Optional[CUnit] = unit
        self.is_none: bool = is_none



        #rel에 활용하기 위함. 또 편리한 검색을 위해.
        self.next_data: Optional[SVNTraceData]= None #다음 버전의 데이터
        self.before_data: Optional[SVNTraceData]= None #이전 버전의 데이터

        self.file_diff: Optional[FileDiff] = None

        self.added_src_node: Dict[str, ClangIndex.Cursor] = {} #이전 버전으로 부터 추가된 노드들
        self.del_src_node: Dict[str, ClangIndex.Cursor] = {} #이전 버전에서 삭제 된 노드들 (이전 Unit의 자식)

        self.before_src_trace_map : Dict[str, SVNTraceData] = {}


    def __str__(self):
        is_none = ''
        if is_none:
            is_none='is_none'

        return f"SVNTraceData({self.revision}, {self.file_path} {is_none})"

    def __repr__(self):
        return self.__str__()

    def generate_key(self) -> RvPath:
        return self.revision, self.file_path

    def to_dict(self) -> Dict:
        return {
            'revision' : self.revision,
            'file_path': self.file_path,
            'repo_path': self.repo_path,
            'is_none': self.is_none,
            'code': self.unit.code
        }

    def update_diff(self, file_diff: FileDiff):
        def update_this_src(unit: CUnit, line_num: int, update_dict: Dict[str, ClangIndex.Cursor] ):
            if unit: #h, cpp 가 아닌 경우 unit이 없음.
                node = unit.get_in_range_node(line_num=line_num)
                if node:
                    src_name = ClangUtill.get_src_name(node)
                    update_dict[src_name] = node


        self.file_diff = file_diff
        line_changes: List[LineChanges] = SVNManager.make_line_changes(file_diff)
        for line_info in line_changes:
            line_num = line_info.line_num

            assert self.before_data, f'{self.revision} {self.file_path}'

            if line_info.action == DiffActionType.Del: #삭제는 이전 노드
                update_this_src(unit = self.before_data.unit, line_num =line_num, update_dict = self.del_src_node)

            elif line_info.action == DiffActionType.Add:  # 추가는 현제 노드
                update_this_src(unit = self.unit, line_num = line_num, update_dict = self.added_src_node)

            src_set = set(self.del_src_node.keys()) | set(self.added_src_node.keys())
            for src in src_set:
                before_src_node = self.before_data.visit_before_src_node(src)
                self.before_src_trace_map[src] = before_src_node


    def visit_before_src_node(self, src_name: str) -> 'SVNTraceData':
        if self.unit is None: #삭제 or 없던 파일
            return self
        elif src_name in self.del_src_node or src_name in self.added_src_node: #src node가 수정되었던 데이터
            return self
        elif self.before_data is None: #더 이상 이전이 없는 경우
            return self
        else:
            return self.before_data.visit_before_src_node(src_name) #이전 데이터 있는 경우 visit 탐색




class SVNTraceProjectData:
    """
    그래프
    """
    def __init__(self, project_path: str, start_rv: Union[int, str], end_rv: [Union, int]):
        self.project_path = project_path
        self.start_rv = start_rv
        self.end_rv = end_rv

        self.rv_path_trace_map: Dict[Tuple[Revision, PathStr], SVNTraceData] = {}#(버전, 파일) : 추적 데이터
        self.path_trace_map: Dict[PathStr, SVNTraceData] = {} #파일경로 : 추적 데이터 (가장 마지막으로 업데이트 된)

        self.__delete_files: Set[str] = set() #중간에 삭제되는 파일 목록
        self.__add_files: Set[str] = set() #중간에 삭제되는 파일 목록

    def __generate_trace_data(self, revision: Revision, file_path: PathStr) -> SVNTraceData:
        '''
        파일의 타입에 따라 처리
        '''
        is_none = False
        if not os.path.isfile(file_path):
            unit = None
            is_none = True

        elif file_path.endswith('.cpp') or file_path.endswith('.h'):
            try:
                print(f'\rparse {file_path}', end='\t')
                unit = CUnit.parse(file_path=file_path)
                print(end='pass')

            except:
                print(f'faill {file_path}')
                raise Exception(f'CUint.parser Error {file_path}') from None
                


        else:
            unit = None

        trace_data = SVNTraceData(revision=revision, file_path=file_path, unit=unit, is_none=is_none)
        key = trace_data.generate_key()
        self.rv_path_trace_map[key] = trace_data
        return trace_data


    def add_data(self, revision: Revision, file_path: PathStr):
        '''
        빈 데이터를 추가하는 용도.
        '''
        #추가된 이력이 있을 경우 수행 x
        key = (revision, file_path)
        if key in self.rv_path_trace_map:
            return
        else: #그외 생성 후 List 연결 처리
            trace_data = self.__generate_trace_data(revision=revision, file_path=file_path)
            if file_path in self.path_trace_map:
                before_trace = self.path_trace_map[file_path]
                before_trace.next_data = trace_data
                trace_data.before_data = before_trace


            self.path_trace_map[file_path] = trace_data


    def update_data(self, file_diff: FileDiff):
        '''
        초기 세팅(베이스 노드?) 이후 호풀. src도 적용
        '''
        file_path = file_diff.file_path
        revision = file_diff.revision

        #중간에 추가된 경우
        if not file_path in self.path_trace_map:
            self.add_data(revision=self.start_rv, file_path=file_path)

        self.add_data(revision=revision, file_path=file_path)

        #항상 마지막 노드를 기준으로 업데이트. 이 후로는 해당 노드가 수정될 일이 없어야함.
        trace_data = self.path_trace_map[file_path]
        if file_path.endswith('.cpp') or file_path.endswith('.h'):
            trace_data.update_diff(file_diff)

