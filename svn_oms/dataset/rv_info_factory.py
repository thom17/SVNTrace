from oms.dataset.info_factory import ClassInfo, VarInfo, FunctionInfo, InfoBase, InfoSet

from svn_oms.dataset.svn_oms import RvInfoBase, RvClassInfo, RvFunctionInfo, RvVarInfo, RvUnit

from clangParser.datas.CUnit import CUnit

from typing import Optional, List, Dict, Union, Tuple, Set

Revision = Union[str, int]
RvInfoType = Union[
    RvInfoBase,
    RvClassInfo,
    RvFunctionInfo,
    RvVarInfo
]

def info2Rvinfo(rv: Revision, info: InfoBase) -> RvInfoType:
    '''
    info에 revision 정보를 추가한 RvInfo 생성.
    '''
    if isinstance(info, ClassInfo):
        return RvClassInfo(info_base=info, revision=rv)
    elif isinstance(info, FunctionInfo):
        return RvFunctionInfo(info_base=info, revision=rv)
    elif isinstance(info, VarInfo):
        return RvVarInfo(info_base=info, revision=rv)
    else:
        return RvInfoBase(info_base=info, revision=rv)

def cunit2RvUnit(rv: Revision, unit: CUnit) -> RvUnit:
    '''
    CUnit을 RvUnit으로 변환.
    '''
    return RvUnit(unit, rv)

def dict2RvUnit(di: dict[str, str], rv: Optional[Revision] = None) -> Optional[RvUnit]:
    '''
    Dict을 RvInfo로 변환.
    '''
    try:
        cunit = CUnit()
        cunit.file_path = di['file_path']
        cunit.code = di['code']
        cunit.file_extension = di['file_extension']
        cunit.file_name = di['file_name']
        if rv is None:
            rv = di['revision']
        return RvUnit(cunit, rv)
    except:
        return None
