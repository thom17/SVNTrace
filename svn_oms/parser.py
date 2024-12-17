from typing import Union, List, Dict, Tuple, Set, Optional
from svn_manager.svn_data import Log, FileDiff, DiffActionType, LineChanges

import svn_manager.svn_data_factory as SVNFactory
import svn_manager.svn_manager as SVNManager
import oms.Mapper as OMS_Mapper
from oms.dataset.info_base import InfoSet,InfoBase

from clang.cindex import Cursor as CindexCursor

import clangParser.clang_utill as ClangUtill
from clangParser.CUnit import CUnit
from filemanager.FolderManager import FolderManager

from collections import defaultdict

from svn_oms.db_handler import DBHandler

def rv_to_int(revision: Union[str]) -> int:
    '''
    to do:
    사실 반드시 구현해야 할것같은대...
    '''

    return int(revision.replace('r', ''))

PathRevision = Tuple[str, str] #file_path, revision

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


        self.log_dif_map: Dict[str, Tuple[Log, List[FileDiff]]] = {}

        #최종 데이터에 활용하는 src와 리비전
        self.src_rv_trace_map: Dict[str, Set[str]] = defaultdict(set)

        #각 리비전의 파싱 unit
        self.path_rv_unit_map : Dict[PathRevision, CUnit] = {}

        #각 리비전에 파싱된 결과
        self.rv_oms_infos: Dict[str, InfoSet] = {}
        self.rv_clang_map: Dict[str, Dict[str, CindexCursor]] = {}



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
            if mode == 'D':
                continue
            else:
                for path in file_path_list:
                    unit = CUnit.parse(path)
                    self.path_rv_unit_map[(path, self.start_rv)] = unit
                    unit_list.append(unit)


        oms_infos, clang_src_map = OMS_Mapper.parsing(cursor_list=unit_list, do_update=False)
        self.rv_oms_infos[self.start_rv] = oms_infos
        self.rv_clang_map[self.start_rv] = clang_src_map

    # def __get_oms(self):


    def __update_rv_map(self, files: List[str], revision: Union[str, int]):
        to_parse_units = []

        #먼저 정상적인 파싱을 위해 모두 업데이트
        for file_path in files:
            SVNManager.do_update(path=file_path, revision=revision)

        #그리고 파싱이력 없는 모델 파싱
        for file_path in files:
            if (file_path, revision) in self.path_rv_unit_map:
                continue
            elif file_path.endswith('.h') or file_path.endswith('.cpp'):
                unit = CUnit.parse(file_path)
                to_parse_units.append(unit)
                self.path_rv_unit_map[(file_path, revision)] = unit

        oms_infos, clang_src_map = OMS_Mapper.parsing(cursor_list=to_parse_units, do_update=False)

        if revision in self.rv_oms_infos:
            print(revision, " dup")
            duplicate_srcs = self.rv_oms_infos[revision].update(oms_infos)
            print(duplicate_srcs)
            duplicate_srcs = self.rv_clang_map[revision].update(clang_src_map)
            print(duplicate_srcs)
        else:
            self.rv_oms_infos[revision] = oms_infos
            self.rv_clang_map[revision] = clang_src_map


    def __trace_diff(self, file_dif_list: List[FileDiff], before_revision: str, revision: str):
        def trace_src(line_changes: List[LineChanges], before_unit: CUnit, cur_unit) -> Dict[DiffActionType, List[str]]:
            action_src_map = defaultdict(set)
            for line_change in line_changes:
                node = None
                if line_change.action == DiffActionType.Del:
                    node = before_unit.get_in_range_node(line_change.line_num)
                else:
                    node = cur_unit.get_in_range_node(line_change.line_num)

                if node:
                    action_src_map[line_change.action].add(ClangUtill.get_src_name(node))


            return action_src_map


        for diff in file_dif_list:
            file_path = diff.filepath
            if file_path.endswith('.cpp') or file_path.endswith('.h'): #다른 파일 파싱될 경우 unit 생성 관련 오류
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
                    before_parse_files.append(diff.filepath)
                elif diff.action == DiffActionType.Add:
                    cur_parse_files.append(diff.filepath)
                else:
                    before_parse_files.append(diff.filepath)
                    cur_parse_files.append(diff.filepath)
            return before_parse_files, cur_parse_files

        self.__parse_start_rv()

        self.log_dif_map = SVNManager.get_svn_range_log_dif(path=self.path, start_revision=self.start_rv, end_revision=self.end_rv)
        target_revisions = list(self.log_dif_map.keys())

        idx = 1
        while idx < len(target_revisions):
            revision = target_revisions[idx]
            before_revision = target_revisions[idx-1]

            log, file_dif_list = self.log_dif_map[revision]
            before_parse_files, cur_parse_files = sep_files_parse(file_dif_list)

            self.__update_rv_map(files=before_parse_files, revision=before_revision)
            self.__update_rv_map(files=cur_parse_files, revision=revision)

            self.__trace_diff(file_dif_list, before_revision, revision)


            print(f'{revision} : {len(file_dif_list)}')
            idx += 1








