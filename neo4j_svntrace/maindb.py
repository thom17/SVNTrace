from typing import List, Dict, Optional
from enum import Enum
import os

from py2neo import Relationship, Node


import neo4j_svntrace.constants as ENodeName


from neo4j_manager.neo4jHandler import Neo4jHandler

import svn_manager.svn_manager as SVNManager
from svn_manager.svn_data import Log, FileDiff

from clangParser.datas.CUnit import CUnit, Cursor
import oms.Mapper as OMSMapper


from svn_oms.dataset.rv_info_factory import RvUnit, info2Rvinfo


PROJECT_PATH = r'D:\dev\AutoPlanning\trunk\AP_trunk_pure'
CYPER_PATH_BY_REVISIONS = \
'''MATCH (n:FileDiff)
WITH n.file_path AS file_path, collect(n.revision) AS revisions
RETURN file_path, revisions
'''

CYPER_GET_FILE_DIFF = \
'''MATCH (n:FileDiff)
WHERE n.filepath = $filepath AND n.revision = $revision
RETURN n
'''
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
        :param revision: 해당 버전을 DB에 저장 (DB에 Log 노드가 있다면 모든 데이터가 있다고 가정 없다면 파싱)
        :return:
        '''
        revision = str(revision)
        if self.__check_revision(revision):
            return
        elif Log.from_subprocess_by_path_with_range(PROJECT_PATH, revision, revision):
            # 파싱을 위해 해당 버전으로 체크아웃
            SVNManager.do_update(PROJECT_PATH, revision)
            log, filediffs = list(SVNManager.get_svn_range_log_dif(PROJECT_PATH, revision, revision).values())[0]

            self.__save_log_diff(log, filediffs)
            for file_diff in filediffs:
                if file_diff.file_path.endswith('.cpp') or file_diff.file_path.endswith('.h'):
                    self.__parse_for_rv(file_diff)
        else:
            print(revision, ' 수정된 파일이 없습니다.')

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
            unit = CUnit.parse(file_path=file_diff.file_path)
            rv_unit = RvUnit(unit, file_diff.revision)

            # Extract RvInfo from the unit
            to_save_data = [rv_unit]
            to_save_relations = []
            for cursor in unit.get_this_Cursor():
                info = OMSMapper.Cursor2InfoBase(cursor)
                if info:
                    rv_info = info2Rvinfo(file_diff.revision, info)
                    to_save_data.append(rv_info)
                    to_save_relations.append((rv_unit, rv_info, 'has'))

            self.neo4j.save_data(to_save_data)
            self.neo4j.add_relationship(to_save_relations)

        except Exception as e:
            print(f"Error parsing {file_diff.file_path} at revision {file_diff.revision}: {e}")
            return None

    def __get_change_infos(self, before_diff: Node, cur_diff: Node) -> Dict[str, Node]:
        info_relations = []

        # 유닛 가져오기
        before_unit = self.get_rv_node_by_path(ENodeName.RV_UNIT, before_diff['revision'], before_diff['file_path'])
        cur_unit = self.get_rv_node_by_path(ENodeName.RV_UNIT, cur_diff['revision'], cur_diff['file_path'])

        assert before_unit and cur_unit, f'이전 유닛({before_diff["revision"]}) 또는 현재 유닛({cur_diff["revision"]})을 찾을 수 없습니다.'

        # info 가져오기
        before_nodes_map = self.get_info_nodes_map(before_unit)
        cur_nodes_map = self.get_info_nodes_map(cur_unit)

        # 먼저 이전 Unit -> 현재 Unit 연결
        for src_name, before_node in before_nodes_map.items():
            next_node = cur_nodes_map.get(src_name, None)

            # case 1. 삭제된 경우
            if next_node is None:
                info_relations.append(Relationship(before_node, 'delete', cur_diff))  # 일단 Diff 에 연결

            # case 2. 수정된 경우
            elif before_node['code'] != next_node['code']:
                info_relations.append(Relationship(before_node, 'modify', next_node))

        # case 3. 추가된 경우
        for src_name, node in cur_nodes_map.items():
            if src_name not in before_nodes_map:
                info_relations.append(Relationship(cur_diff, 'add', node))

        return info_relations

    def get_info_nodes_map(self, rvunit: Node):
        infos = [r.end_node for r in self.neo4j.graph.match((rvunit, None), r_type='has')]
        infos_map = {}
        for info in infos:
            assert info['src_name'] not in infos_map, f'중복된 src_name 발견 {info["src_name"]}'
            infos_map[info['src_name']] = info
        return infos_map


    def update_trace(self):
        '''
        현제 저장된  FileDiff를 기준으로 추적 갱신.
        기존 연결과 동일하지 않다면 RvInfo 도 추적
        '''
        def __get_connect_relationship(path: str, revision_list: list[str]):
            # 연결된 노드가 없을 경우
            before = None
            next = None
            relations_list = []
            for revision in revision_list:
                #to do : 해당 리비전의 FileDiff 노드 가져오기
                node = self.get_rv_node_by_path(ENodeName.FILE_DIFF, revision, path)
                if before:
                    # to do : 기존 연결된 노드가 있고 동일할 경우 스킵
                    existing_rels = list(self.neo4j.graph.match((before, None), r_type='next'))
                    if existing_rels:
                        # 기존 연결된 노드가 있고 동일할 경우 스킵
                        if existing_rels[0].end_node == node and existing_rels[0].start_node == before:
                            continue

                    relations_list.append( Relationship(before, 'next' ,node) )
                    relations_list.extend( self.__get_change_infos(before, node) )


                before = node
            return relations_list



        #파일별 리비전 리스트 가져오기
        result = self.neo4j.do_query(CYPER_PATH_BY_REVISIONS)
        for path_revisions_dict in result:
            path = path_revisions_dict['file_path']
            revisions = path_revisions_dict['revisions']
            revisions.sort(reverse=False)

            relations = __get_connect_relationship(path, revisions)


            #일단 임시로 하나만 태스트
            tx = self.neo4j.graph.begin()
            try:
                for rel in relations:
                    tx.create(rel)
                tx.commit()
            except Exception as e:
                tx.rollback()
                raise e
            break


        print(result)

    def get_rv_node_by_path(self, node_name: str, revision: str, filepath : str) -> Optional[Node]:
        nodes = []
        for node in list(self.neo4j.graph.nodes.match(node_name, revision=revision)):
            if os.path.normpath(node['file_path']) == os.path.normpath(filepath):
                nodes.append(node)

        if not nodes:
            return None
        elif len(nodes) == 1:
            return nodes[0]
        else:
            raise Exception(f"Multiple nodes found for revision {revision} and file {filepath} {len(nodes)}")

    def update_file_path_normalize(self):
        '''
        DB에 저장된 파일 경로를 정규화합니다.
        // , / , \ 등으로 저장된 경로를 통일합니다.
        :return:
        '''
        query = """
            MATCH (n)
            WHERE n.file_path is NOT NULL
            RETURN n, n.file_path AS file_path
            """
        result = self.neo4j.do_query(query)
        tx = self.neo4j.graph.begin()
        change_size = 0
        for record in result:
            node = record["n"]
            old_path = record["file_path"]
            new_path = os.path.normpath(old_path)
            if old_path != new_path:
                change_size += 1
                tx.run("MATCH (n) WHERE ID(n) = $node_id SET n.file_path = $new_path",
                       node_id=node.identity, new_path=new_path)
        tx.commit()
        print(f"Updated {change_size} file paths to normalized format.")