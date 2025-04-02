from typing import List, Dict

from neo4j_manager.neo4jHandler import Neo4jHandler

import svn_manager.svn_manager as SVNManager
from svn_manager.svn_data import Log, FileDiff

from clangParser.datas.CUnit import CUnit, Cursor
import oms.Mapper as OMSMapper


from svn_oms.dataset.rv_info_factory import RvUnit, info2Rvinfo


PROJECT_PATH = r'D:\dev\AutoPlanning\trunk\AP_trunk_pure'


class MainDBManager:
    '''
    Neo4j DB를 관리하는 클래스
    DB에 해당 데이터가 저장되어있는지 확인하고, 없으면 저장합니다.
    '''

    def __init__(self, uri="bolt://localhost:7687", user="neo4j", database='merge', password="123456789"):
        self.neo4j: Neo4jHandler = Neo4jHandler(uri=uri, user=user, password=password, database=database)

    def __check_revision(self, revision: str) -> bool:
        '''
        :param revision: 해당 버전이 DB에 저장되어있는지 확인
        :return: True or False
        '''
        query = "MATCH (log:Log) WHERE log.revision = $revision RETURN log"
        result = self.neo4j.graph.run(query, {"revision": revision}).data()
        if not result:
            return False
        elif len(result) == 1:
            return True
        else:
            raise Exception(f"Multiple nodes found for revision {revision} {len(result)}")


    def update_revision(self, revision: str):
        '''
        :param revision: 해당 버전을 DB에 저장
        :return:
        '''

        if self.__check_revision(revision):
            return
        else:
            # 파싱을 위해 해당 버전으로 체크아웃
            SVNManager.do_update(PROJECT_PATH, revision)
            log, filediffs = list(SVNManager.get_svn_range_log_dif(PROJECT_PATH, revision, revision).values())[0]

            self.__save_log_diff(log, filediffs)
            for file_diff in filediffs:
                if file_diff.filepath.endswith('.cpp') or file_diff.filepath.endswith('.h'):
                    self.__parse_for_rv(file_diff)

    def __save_log_diff(self, log: Log, filediffs: List[FileDiff]):
        save_datas = [log] + filediffs
        save_relations = []

        for file_diff in filediffs:
            save_relations.append((log, file_diff, 'file_diff'))

        self.neo4j.save_data(save_datas)
        self.neo4j.add_relationship(save_relations)

    def __parse_for_rv(self, file_diff: FileDiff):
        '''
        :param file_diff:
        :return:
        '''

        try:
            # Parse the file and create RvUnit
            unit = CUnit.parse(file_path=file_diff.filepath)
            rv_unit = RvUnit(unit, file_diff.revision)

            # Extract RvInfo from the unit
            to_save_data = [rv_unit]
            to_save_relations = []
            for cursor in unit.get_this_Cursor():
                info = OMSMapper.Cursor2InfoBase(cursor)
                if info:
                    to_save_data.append(info2Rvinfo(file_diff.revision, info))
                    to_save_relations.append((rv_unit, info, 'has'))

            self.neo4j.save_data(to_save_data)
            self.neo4j.add_relationship(to_save_relations)

        except Exception as e:
            print(f"Error parsing {file_diff.filepath} at revision {file_diff.revision}: {e}")
            return None



    def get_rv_unit(self, revision: str, filepath: str):
        '''
        :param revision:
        :param filepath:
        :return:
        '''
        query = "MATCH (unit:A) WHERE unit.revision = $revision AND unit.file_path = $filepath RETURN unit"
        result = self.neo4j.graph.run(query, {"revision": revision, "filepath": filepath}).data()
        if not result:
            return None
        elif len(result) == 1:
            return result[0]['unit']
        else:
            raise Exception(f"Multiple nodes found for revision {revision} and file {filepath} {len(result)}")
