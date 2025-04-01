from typing import Optional, List, Dict, Union, Tuple, Set

import clang.cindex as ClangIndex

from clangParser.datas.CUnit import CUnit

from oms.dataset.class_info import ClassInfo
from oms.dataset.function_info import FunctionInfo

from oms.dataset.info_base import InfoBase, InfoSet, RelationInfo
import oms.Mapper as Mapper

PathStr = str
Revision = Union[str, int]

RvPath = Tuple[Revision, PathStr]

rv_src_sep = '#'

class RvInfoBase:
    def __init__(self, info_base: InfoBase, revision: str):
        self.info_base = info_base
        self.revision:str = revision
        self.rv_src:str = self.revision + rv_src_sep + self.info_base.src_name

        self.owner = None # 일단 None으로 처리
        # self.relationInfo = RvRelationInfo()


    def to_dict(self):
        info_dict = self.info_base.to_dict()
        info_dict['revision'] = self.revision
        return info_dict

    def __str__(self):
        return self.rv_src

    def __repr__(self):
        return self.__str__()

class RvUnit:
    def __init__(self, cunit: CUnit, revision: str):
        self.cunit: CUnit = cunit
        self.revision = revision
        self.rv_src = self.revision + rv_src_sep + self.cunit.file_path

    def __str__(self):
        return self.rv_src

    def to_dict(self):
        source_dict = self.cunit.to_dict()
        source_dict['revision'] = self.revision
        source_dict['rv_src'] = self.rv_src
        return source_dict



class RvClassInfo(RvInfoBase):
    pass

class RvFunctionInfo(RvInfoBase):
    pass

class RvVarInfo(RvInfoBase):
    pass



class RevisionInfoSet:
    '''
    관리하는 Revision 관련 정보들을 처리하는 클래스
    '''

    def __init__(self):
        self.__RvInfo_mp: Dict[str, RvInfoBase] = {}  # key = "revision:source"
        self.__rv_info_map: Dict[Revision, InfoSet] = {}  # key = Revision
        self.__src_rv_set: Dict[str, Set[Revision]] = {}  # key = source

    def add_revision_info(self, revision: str, source: str, info: RvInfoBase):
        """
        새로운 Revision 정보를 추가합니다.

        Args:
            revision (str): Revision 식별자.
            source (str): Source 식별자.
            info (RvInfoBase): Revision에 대한 정보.
        """
        key = f"{revision}:{source}"
        self.__RvInfo_mp[key] = info

        if revision not in self.__rv_info_map:
            self.__rv_info_map[revision] = InfoSet()
        self.__rv_info_map[revision].put_info(info.info_base)

        if source not in self.__src_rv_set:
            self.__src_rv_set[source] = set()
        self.__src_rv_set[source].add(revision)

    def get_RvInfo(self, revision: str, src: str) -> RvInfoBase:
        """
        특정 Revision과 Source에 해당하는 정보를 반환합니다.

        Args:
            revision (str): Revision 식별자.
            src (str): src 식별자.

        Returns:
            RvInfoBase: 해당 Revision과 Source에 대한 정보.
        """
        key = f"{revision}{rv_src_sep}{src}"
        return self.__RvInfo_mp.get(key)

    def get_base_Infoset(self, revision: str) -> InfoSet:
        """
        특정 Revision에 해당하는 InfoSet을 반환합니다.

        Args:
            revision (str): Revision 식별자.

        Returns:
            InfoSet: 해당 Revision에 대한 InfoSet.
        """
        return self.__rv_info_map.get(revision)

    def get_src_revision_set(self, src: str) -> List[Revision]:
        """
        같은 src를 가지는 Revision 셋을 반환합니다.

        Args:
            src (str): src 식별자.

        Returns:
            List[Revision]: 해당 src 대한 Revision 셋.
        """
        return self.__src_rv_set.get(src, [])



# class RvRelationInfo:
#     def __init__(self):
#         self.callInfoMap = InfoSet()
#         self.callByInfoMap = InfoSet()
#         self.hasInfoMap = InfoSet()
#
#         #추후 확장을 고려하여
#         self.infoMap: [str, InfoSet] = {}
#         self.infoMap["call"] = self.callInfoMap
#         self.infoMap["callBy"] = self.callByInfoMap
#         self.infoMap["has"] = self.hasInfoMap
#
#     def __str__(self):
#         this_str = 'RelationInfo('
#         for relation_name, info_set in self.infoMap.items():
#             this_str += f'\n\t{relation_name}:{info_set}'
#         this_str += '\t)'
#         return this_str
#
#     def __repr__(self):
#         return self.__str__()
#
#     def __len__(self):
#         le = 0
#         for info_set in self.infoMap.values():
#             le += len(info_set)
#         return le

