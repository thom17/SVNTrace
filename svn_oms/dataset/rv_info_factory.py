from oms.dataset.info_factory import ClassInfo, VarInfo, FunctionInfo, InfoBase, InfoSet

from svn_oms.dataset.svn_oms import RvInfoBase, RvClassInfo, RvFunctionInfo, RvVarInfo


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

