from typing import Union, List, Dict, Tuple, Set, Optional
from svn_manager.svn_data import Log, FileDiff, DiffActionType, LineChanges

import svn_manager.svn_data_factory as SVNFactory
import svn_manager.svn_manager as SVNManager
import oms.Mapper as OMS_Mapper
from oms.dataset.info_base import InfoSet,InfoBase

from clang.cindex import Cursor as CindexCursor

import clangParser.clang_utill as ClangUtill
from clangParser.datas.CUnit import CUnit, Cursor

from filemanager.FolderManager import FolderManager

from collections import defaultdict

from svn_oms.db_handler import DBHandler
'''
12-18
너무 복잡하다....
칼들고 나를 협박해서 아래의 과제를 수행하자.

1. CUnit을 생성하고 생성된 시점의 코드를 unit에 저장해두자. 
일단 이걸로 업데이트 순서를 지켜야되는 복잡도가 확 줄어든다. 또 너무 오래걸리지 않는듯. (하나의 파일 에대 max 8~10초 정도?)

2. SVNDataSet 에 기본적으로 파싱한 데이터를 다 때려 넣자.
모든 데이터 셋, 관계 데이터 셋 등 일단 이를 통해 중간 데이터도 DB화를 고려하자.
핵심적으로 db / parser의 입 출력으로 활용하자.

'''


def rv_to_int(revision: Union[str]) -> int:
    '''
    to do:
    사실 반드시 구현해야 할것같은대...
    '''

    return int(revision.replace('r', ''))

PathRevision = Tuple[str, str] #file_path, revision


class SVNDataSet:
    '''
    Simplified structure using two sets:
    - units: stores (revision, path, unit)
    - srcs: stores (src, revision)
    '''
    def __init__(self):
        self.rv_path_units: Dict[Tuple[str, str], CUnit] = {}  # rv-path-unit
        self.rv_srcs: Set[Tuple[str, str]] = set()  # rv-src

        self.none_rv_files: Set[Tuple[str, str]] = set() #(삭제된 버전 , 삭제 된 파일) 혹은 (생성 되기 전 버전, 생성된 파일)

        self.unit_rels: Dict[str, List[Tuple[CUnit, CUnit]]] = defaultdict(list) #type, [unit-unit]
        self.src_rels: Dict[str, List[Tuple[CUnit, CUnit]]] = defaultdict(list) #type, [unit-unit]

    def get_path_units_rvs(self) -> Dict[str, List[Tuple[CUnit, str]]]:
        path_unit_rvs: Dict[str, List[Tuple[CUnit, str]]] = defaultdict(list)
        for (rv, path), unit in self.rv_path_units.items():
            path_unit_rvs[path].append((unit, rv))
        return dict(path_unit_rvs)


    def add_unit(self, revision: str, path: str, unit: CUnit):
        self.rv_path_units[(revision, path)] = unit

    def get_rv_path_map(self) -> Dict[str, Set[str]]:
        """
        Generate a map of revision -> paths.
        """
        rv_path_map = defaultdict(set)
        for (rv, path), _ in self.rv_path_units.items():
            rv_path_map[rv].add(path)
        return dict(rv_path_map)

    def get_path_rv_map(self) -> Dict[str, Set[str]]:
        """
        Generate a map of path -> revisions.
        """
        path_rv_map = defaultdict(set)
        for (rv, path), _ in self.rv_path_units.items():
            path_rv_map[path].add(rv)
        return dict(path_rv_map)

    def get_src_rv_map(self) -> Dict[str, Set[str]]:
        """
        Generate a map of src -> revisions.
        """
        src_rv_map = defaultdict(set)
        for rv, src in self.rv_srcs:
            src_rv_map[src].add(rv)
        return dict(src_rv_map)

    def get_rv_src_map(self) -> Dict[str, Set[str]]:
        """
        Generate a map of revision -> srcs.
        """
        rv_src_map = defaultdict(set)
        for rv, src in self.rv_srcs:
            rv_src_map[rv].add(src)
        return dict(rv_src_map)
    def get_last_units_map(self, file_paths: List[str], cur_revision: str ) -> Dict[str, Tuple[CUnit, str]]:
        last_units: Dict[str, Tuple[CUnit, str]] = {}
        path_rvs_map = self.get_path_rv_map()
        for path in file_paths:
            if path in path_rvs_map:
                sorted_revs = sorted(list(path_rvs_map[path]), reverse=True)
                last_rv = sorted_revs[0]
                assert SVNManager.get_before_change_rv(path=path, revision=cur_revision), f'{cur_revision} {path}???'
                last_unit = self.rv_path_units[(last_rv, path)]
                last_units[path] = (last_unit, last_rv)
            else: #cur_revision에 추가된 데이터
                before_revision = str(int(cur_revision)-1)
                self.none_rv_files.add((before_revision, path))

        return last_units

    def add_rel(self, start_src_or_unit, end_src_or_unit: Union[str, CUnit], rel_name: str):
        assert type(start_src_or_unit) == type(end_src_or_unit) or not start_src_or_unit or not end_src_or_unit, f'서로 다른 타입의 연결. '
        if isinstance(start_src_or_unit, str):
            self.src_rels[rel_name].append((start_src_or_unit, end_src_or_unit))
        else:
            self.unit_rels[rel_name].append((start_src_or_unit, end_src_or_unit))



class SVNProjectParser:
    def __init__(self, path: str, start_rv: Union[int, str] = None, end_rv :[Union, int] = 'HEAD'):
        self.path = path
        self.start_rv = start_rv
        self.end_rv = end_rv

        self.start_rv_num = 0
        if self.start_rv:
            self.start_rv_num = rv_to_int(self.start_rv)

        self.end_rv_num = None
        if self.end_rv != 'HEAD':
            self.end_rv_num = rv_to_int(self.end_rv)

        self.data_set = SVNDataSet()


        self.log_dif_map: Dict[str, Tuple[Log, List[FileDiff]]] = {}

        # #최종 데이터에 활용하는 src와 리비전
        # self.src_rv_trace_map: Dict[str, Set[str]] = defaultdict(set)
        #
        # #각 리비전의 파싱 unit
        # self.path_rv_unit_map : Dict[PathRevision, CUnit] = {}
        #
        # #각 리비전에 파싱된 결과
        # self.rv_oms_infos: Dict[str, InfoSet] = {}
        # self.rv_clang_map: Dict[str, Dict[str, CindexCursor]] = {}



    def __is_target_rv(self, rv_num : int):
        if self.start_rv_num <= rv_num and (self.end_rv_num is None or rv_num <= self.end_rv_num):
            return True
        else:
            return False

    def get_target_revisions(self) -> List[str]:
        target_revision = []

        revisions = SVNManager.get_repo_revisions(path=self.path)
        for rv in revisions:
            rv_num = rv_to_int(rv)
            if self.__is_target_rv(rv_num=rv_num):
                target_revision.append(rv)
        return target_revision

    def __get_rv_info(self, src: str, rv: str) -> Optional[InfoBase]:
        return self.rv_oms_infos[rv].get_info(src_name=src)

    def __get_rv_infos_map(self) -> Dict[str, List[InfoBase]]:
        '''
        db_handler는 save_data(infos, rv)
        이에 맞는 데이터를 저장하는 구조를 생성
        <rv infos>
        '''
        rv_infos_map: Dict[str, List[InfoBase]] = defaultdict(list)

        #시작 리비전은 예외적으로 추가
        def make_start_info():
            for src in self.src_rv_trace_map:
                info = self.rv_oms_infos[self.start_rv].get_info(src)
                if info:
                    rv_infos_map[self.start_rv].append(info)

        make_start_info()

        revisions = [rv for rv in self.log_dif_map.keys() if rv != self.start_rv]
        for rv in revisions:
            rv_info_set = self.rv_oms_infos[rv]
            for src, rv_set in self.src_rv_trace_map.items():
                if rv in rv_set: #해당 리비전에 수정되어야 포함
                    info = rv_info_set.get_info(src)

                    #sig가 변경되거나 제거된 경우
                    if info == None:
                        print(f'{src} {rv} 에 trace map에 저장되었으나 검색이 안되는 경우 발생')
                    else:
                        rv_infos_map[rv].append(info)
        return rv_infos_map


    def save_db(self, db_handler: DBHandler):
        #일단 먼저 배경이 되는 노드들을 생성 및 저장
        rv_infos = self.__get_rv_infos_map()
        idx = 0
        for rv, infos in rv_infos.items():
            print(f'\r {idx}/{len(rv_infos)} : r{rv} : {len(infos)} infos', end="")
            db_handler.save_data(data_list=infos, revision=rv)
        print(f'\r {idx}/{len(rv_infos)} : r{rv} : {len(infos)} infos')

        #일단은 여기서 추적 맵을 생성하고
        def get_update_trace(src: str, revision_set: Set[str]):
            info_list = []
            revision_list = sorted(list(revision_set))
            for rv in revision_list:
                info = self.__get_rv_info(src, rv)
                assert info, f'{src} : {rv} 찾을 수 없는 info'
                info_list.append(info)

            if not self.start_rv in revision_list:
                start_info = self.__get_rv_info(src, self.start_rv)
                if start_info:
                    info_list = [start_info] + info_list
                    revision_list = [self.start_rv] + revision_list

            return info_list, revision_list




    #초기 버전은 그냥 모든 노드를 저장해야함. 최소한의 이전 노드가 되기 위함임.
    def __parse_start_rv(self):
        #종료 버전으로 업데이트
        SVNManager.do_update(path=self.path, revision=self.end_rv)

        #시작 버전으로 업데이트. (총 수정 파일을 반환받음)
        update_result = SVNManager.do_update(path=self.path, revision=self.start_rv)

        unit_list = []
        for mode, file_path_list in update_result.items():
            file_path_list = [path for path in file_path_list if path.endswith('.cpp') or path.endswith('.h')]
            if mode == 'D':
                for path in file_path_list:
                    self.data_set.none_rv_files.add((self.start_rv, path))
                print(f'start - end 사이에 추가되는 파일  {len(file_path_list)}개 있음.{self.start_rv} - {self.end_rv}')
            else:
                for path in file_path_list:
                    unit = CUnit.parse(path)
                    self.data_set.add_unit(path=path, revision=self.start_rv, unit=unit)


    # def __get_oms(self):


    def __update_rv_map(self, files: List[str], revision: Union[str, int]):
        to_parse_units = []

        #먼저 정상적인 파싱을 위해 모두 업데이트
        for file_path in files:
            SVNManager.do_update(path=file_path, revision=revision)

        #그리고 파싱이력 없는 모델 파싱
        for file_path in files:
            if (file_path, revision) in  self.data_set.rv_path_units:
                continue
            elif file_path.endswith('.h') or file_path.endswith('.cpp'):
                unit = CUnit.parse(file_path)
                self.data_set.add_unit(revision=revision, path=file_path, unit=unit)


    def __trace_diff(self, file_dif_list: List[FileDiff], before_revision: str, revision: str):
        def get_before_unit(diff: FileDiff):
            file_path = diff.file_path
            revision = diff.revision

            #이 코드는 반드시 성공해야함. 수정된 파일만 호출하도록 설계했음.
            before_revision = SVNManager.get_before_change_rv(path=file_path, revision=revision)

            if (before_revision, file_path) in self.data_set.rv_path_units:
                return self.data_set.rv_path_units[(before_revision, file_path) ]
            elif (self.start_rv, file_path) in self.data_set.rv_path_units:
                return self.data_set.rv_path_units[(self.start_rv, file_path) ]

        def trace_src(line_changes: List[LineChanges], before_unit: CUnit, cur_unit) -> Dict[
            DiffActionType, List[str]]:
            action_src_map = defaultdict(set)
            for line_change in line_changes:
                node = None
                unit = None
                if line_change.action == DiffActionType.Del:
                    node = before_unit.get_in_range_node(line_change.line_num)
                    unit = before_unit
                else:
                    node = cur_unit.get_in_range_node(line_change.line_num)
                    unit = cur_unit

                if node:
                    # OMS_Mapper.Cursor2OMS(Cursor(node, source_code=unit.code), )
                    # =Cursor(node, source_code=unit.code)
                    action_src_map[line_change.action].add(ClangUtill.get_src_name(node))


            return action_src_map


        for diff in file_dif_list:
            file_path = diff.file_path
            if file_path.endswith('.cpp') or file_path.endswith('.h'): #다른 파일 파싱될 경우 unit 생성 관련 오류
                if diff.action == DiffActionType.Add:
                    pass
                elif diff.action == DiffActionType.Del:
                    pass
                else:
                    before_unit = get_before_unit(diff)
                    cur_unit = self.data_set.rv_path_units[(diff.revision, diff.file_path)]

                    SVNManager.make_line_changes(diff)



                before_revision =SVNManager.get_before_change_rv(path=file_path, revision=revision)


                before_unit = self.path_rv_unit_map.get((file_path, before_revision), None)
                cur_unit = self.path_rv_unit_map.get((file_path, revision), None)

                line_changes = SVNFactory.make_line_changes(diff)
                action_src_map = trace_src(line_changes=line_changes, before_unit=before_unit, cur_unit=cur_unit)

                print(file_path)
                for act, srcs in action_src_map.items():
                    print(f'{act} {srcs}')
                    for src in srcs:
                        self.src_rv_trace_map[src].add(revision)

    def parse(self):
        def sep_files_parse(diff_list: List[FileDiff]) -> Tuple[List[str], List[str]]:
            cur_parse_files = []
            before_parse_files = []
            for diff in diff_list:
                if diff.action == DiffActionType.Del:
                    before_parse_files.append(diff.file_path)
                elif diff.action == DiffActionType.Add:
                    cur_parse_files.append(diff.file_path)
                else:
                    before_parse_files.append(diff.file_path)
                    cur_parse_files.append(diff.file_path)

            before_parse_files = [path for path in before_parse_files if path.endswith('.cpp') or path.endswith('.h')]
            cur_parse_files = [path for path in cur_parse_files if path.endswith('.cpp') or path.endswith('.h')]

            return before_parse_files, cur_parse_files

        self.__parse_start_rv()

        self.log_dif_map = SVNManager.get_svn_range_log_dif(path=self.path, start_revision=self.start_rv, end_revision=self.end_rv)
        target_revisions = list(self.log_dif_map.keys())

        idx = 1
        while idx < len(target_revisions):
            revision = target_revisions[idx]

            log, file_dif_list = self.log_dif_map[revision]
            before_parse_files, cur_parse_files = sep_files_parse(file_dif_list)

            before_unit_map: Dict[str, Tuple[CUnit, str]] = self.data_set.get_last_units_map(file_paths = before_parse_files, cur_revision=revision)
            self.__update_rv_map(files=cur_parse_files, revision=revision)
            update_unit_map: Dict[str, Tuple[CUnit, str]] = self.data_set.get_last_units_map(file_paths = cur_parse_files, cur_revision=revision)

            for path, (before_unit, rv) in before_unit_map.items():
                if path in update_unit_map: #수정된 경우.
                    unit = update_unit_map[path][0]
                    self.data_set.add_rel(before_unit, unit, 'update')
                else: #삭제된 경우 임
                    self.data_set.add_rel(before_unit, None, 'del')

            #업데이트 쪽 파일에는 있으나 이전 버전에 없을 경우
            for path, (unit, rv) in update_unit_map.items():
                if not path in before_unit_map:
                    self.data_set.add_rel(None, unit, 'add') #해당 파일은 중간에 추가된 경우임

            self.__trace_diff(file_dif_list=file_dif_list, revision=revision)

            print(f'{revision} : {len(file_dif_list)}')
            idx += 1








