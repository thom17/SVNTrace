import oms.Mapper as OMSMapper
from oms.info_set import InfoSet
from clangParser.CUnit import CUnit


def parse_data():
    path = r'D:\dev\AutoPlanning\trunk\Ap-Trunk-auto-task\mod_APImplantSimulation\\'
    units=CUnit.parse_project(path)
    return units


def test_gen():
    info_set = InfoSet()
    infos = set()
    for unit in parse_data():
        for node in unit.this_file_nodes:
            info = OMSMapper.Cursor2InfoBase(node)
            info_set.put_info(info)
            infos.add(info)
    print(info_set)
    print(infos)

