from typing import List, Dict, Optional
from enum import Enum
import os

from py2neo import Relationship, Node


import neo4j_svntrace.constants as ENodeName


from neo4j_manager.neo4jHandler import Neo4jHandler

import svn_managers.svn_manager as SVNManager
from svn_managers.svn_data import Log, FileDiff

from clangParser.datas.CUnit import CUnit, Cursor
import oms.Mapper as OMSMapper


from svn_oms.dataset.rv_info_factory import RvUnit, info2Rvinfo

PROJECT_PATH = r'D:\dev\AutoPlanning\forDB'
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
class TraceDataBase:
    '''
    Neo4j DB를 관리하는 클래스
    DB에 해당 데이터가 저장되어있는지 확인하고, 없으면 저장합니다.
    '''

    def __init__(self, uri="bolt://localhost:7687", user="neo4j", database='test', password="123456789", local_path=PROJECT_PATH):
        self.neo4j: Neo4jHandler = Neo4jHandler(uri=uri, user=user, password=password, database=database)
        self.database: str = database  # 현재 DB명 보관
        self.local_path: str = local_path  # 현재 프로젝트 경로 보관
        self.repo_path: str = SVNManager.get_repo_url(self.local_path)

    # --- 위임/헬퍼 메서드 추가 ---
    def get_db_names(self) -> List[str]:
        return self.neo4j.get_db_names()

    def get_node_count(self) -> int:
        return self.neo4j.get_node_count()

    def get_last_modified(self) -> str:
        return self.neo4j.get_last_modified()

    def print_info(self):
        return self.neo4j.print_info()


    # #db rv 와 path rv 쌍 가져오기
    # def get_head_rv_pair(self) -> tuple[str, str]:
    #     '''
    #     to do:
    #     로컬 패스를 가져와야함
    #     1. head노드에 프로젝트 경로 추가해야함
    #     2. 프로젝트 경로를 객체마다 받도록 수정해야함 (현제는 상수 값 사용)
    #     3. 리비전 종류가 3개임 (DB, 로컬, repo).
    #     4. 그냥 각각 가져오는 메서드를 정의하는게 나을듯
    #     '''
    #     query = "MATCH (h:Head) return h"
    #     result = self.neo4j.do_query(query)
    #     if result:
    #         db_rv = result[0]['h']['revision']
    #         local_path = result[0]['h']['project_path']
    #         SVNManager.get
    #     else:
    #         db_rv = None

    def get_head_revision(self) -> Optional[str]:
        '''
        DB의 head 노드의 revision을 반환합니다.
        :return: revision or None
        '''
        query = "MATCH (h:Head) return h"
        result = self.neo4j.do_query(query)
        return result[0]['h']['revision'] if result else None




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
            to_save_relations = [(file_diff, rv_unit, 'unit')]
            for cursor in unit.get_this_Cursor():
                #class a; 와 같은 단순한 클래스 선언은 제외
                if cursor.kind == 'CLASS_DECL' and len(cursor.get_children()) == 0:
                    continue
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

        if not before_unit and cur_unit:
            # 이전 유닛이 없고 현재 유닛만 있는 경우(추가된 경우)
            before_unit = self.get_rv_node_by_path(ENodeName.RV_UNIT, before_diff['revision'], before_diff['file_path'])

        # assert before_unit and cur_unit, f'{cur_diff["file_path"]} 이전 유닛({before_diff["revision"]}) 또는 현재 유닛({cur_diff["revision"]})을 찾을 수 없습니다.'

        # info 가져오기
        if before_unit:
            before_nodes_map = self.get_info_nodes_map(before_unit)

        if cur_unit:
            cur_nodes_map = self.get_info_nodes_map(cur_unit)

        # 먼저 이전 Unit -> 현재 Unit 연결 (파일 수정)
        if before_unit and cur_unit:
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
        #파일 추가된 경우
        elif not before_unit and cur_unit:
            for src_name, node in cur_nodes_map.items():
                info_relations.append(Relationship(cur_diff, 'add', node))
        #파일 삭제된 경우
        elif before_unit and not cur_unit:
            for src_name, node in before_nodes_map.items():
                info_relations.append(Relationship(node, 'delete', cur_diff))

        return info_relations

    def get_info_nodes_map(self, rvunit: Node):
        infos = [r.end_node for r in self.neo4j.graph.match((rvunit, None), r_type='has')]
        infos_map = {}
        for info in infos:
            #임시방편으로 일단 긴거 선택. 추후 저장 시 필터링 해야할듯. https://github.com/thom17/SVNTrace/issues/5
            if info['src_name'] in infos_map:
                print(f'중복된 src_name 발견 {info["revision"]} {info["src_name"]}')
                if len(info['code']) < len(infos_map[info['src_name']]['code']):
                    info = infos_map[info['src_name']]
            #아무튼 info 설정
            infos_map[info['src_name']] = info
        return infos_map

    def reconnect_trace_relationship(self):
        '''
        기존 연결된 노드정보를 모두 삭제하고 재연결
        '''

        #기존 연결된 노드 삭제
        query = "MATCH ()-[r]->() DELETE r"
        self.neo4j.do_query(query)

        #Log 가져와서 리비전 순으로 정렬
        query ="""
        MATCH (n:Log)
        WITH n ORDER BY n.revision
        WITH collect(n) AS logs
        UNWIND range(0, size(logs)-2) AS i
        WITH logs[i] AS from, logs[i+1] AS to
        MERGE (from)-[:next_log]->(to)
        """
        self.neo4j.do_query(query)
        print(f"Log-Log 연결 완료")


        #Log - FileDiff  노드 연결
        query = """
        MATCH (l:Log), (f:FileDiff)
        WHERE l.revision = f.revision
        MERGE (l)-[:file_diff]->(f)
        """
        self.neo4j.do_query(query)
        print(f"Log-FileDiff 연결 완료")

        #FileDiff - RvUnit 노드 연결
        query = """
            MATCH (f:FileDiff), (r:RvUnit)
            WHERE f.file_path = r.file_path AND f.revision = r.revision
            MERGE (f)-[:unit]->(r)
            """
        self.neo4j.do_query(query)
        print(f"FileDiff-RvUnit 연결 완료")


        #FileDiff - FileDiff 노드 연결
        query = """
            MATCH (n:FileDiff)
            WITH n.file_path AS file_path, collect(n) AS files
            UNWIND files AS file
            WITH file_path, file
            ORDER BY file_path, file.revision
            WITH file_path, collect(file) AS sorted_files
            UNWIND range(0, size(sorted_files)-2) AS i
            WITH sorted_files[i] AS from, sorted_files[i+1] AS to
            MERGE (from)-[:next_diff]->(to)
                """
        self.neo4j.do_query(query)
        print(f"FileDiff-FileDiff 연결 완료")

        #Set RvInfo
        self.neo4j.do_query("MATCH (n:RvClassInfo) SET n:RvInfo")
        self.neo4j.do_query("MATCH (n:RvFunctionInfo) SET n:RvInfo")
        self.neo4j.do_query("MATCH (n:RvVarInfo) SET n:RvInfo")

        #RvUnit - RvInfo 노드 연결
        query = """
        MATCH (r:RvUnit)
        MATCH (n:RvInfo {revision: r.revision, file_path: r.file_path})
        MERGE (r)-[:has]->(n)
        """
        self.neo4j.do_query(query)
        print(f"RvUnit-RvInfo 연결 완료")
        
        #RvInfo - RvInfo 노드 연결
        query = """
        MATCH (f:FileDiff)
        WITH f.file_path AS file_path, f
        ORDER BY f.revision
        WITH file_path, collect(f) AS sorted_file_diff
        RETURN file_path, sorted_file_diff
        """
        path_rvinfo_trace_map: dict[str, list[Relationship]] = {} #파일별 rvinfo relationship

        #1. 먼저 FileDiff rv 순으로 가져옴
        for results in self.neo4j.do_query(query):
            file_path = results['file_path']
            sorted_file_diff = results['sorted_file_diff']
            path_rvinfo_trace_map[file_path] = []
            #2. 두개의 FileDiff로 RvOMSTrace 및 Relationship 생성
            for i in range(1, len(sorted_file_diff)):
                file_diff_1 = sorted_file_diff[i - 1]
                file_diff_2 = sorted_file_diff[i]
                path_rvinfo_trace_map[file_path].extend(self.__get_change_infos(file_diff_1, file_diff_2))
        #3. 생성된 Relationship을 DB에 저장
        for file_path, relations in path_rvinfo_trace_map.items():
            tx = self.neo4j.graph.begin()
            for rel in relations:
                tx.create(rel)
            tx.commit()
            print(f'RvInfo 연결: {file_path}'"")

        #4. 위에서 생성한 Relationship을 바탕으로 Log - RvInfo 연결
        query = """
            MATCH (n1:RvInfo)-[:modify]->(n2:RvInfo)
            MATCH (l1:Log {revision: n1.revision}), (l2:Log {revision: n2.revision})
            MERGE (n1)-[:log]->(l1)
            MERGE (n2)-[:log]->(l2)
            """
        self.neo4j.do_query(query)
        print(f'RvInfo - Log 연결 완료')

        # for node in self.neo4j.graph.nodes.match('RvInfo'):

    def connect_head_info(self):
        '''
        head 노드를 생성 및 데이터와 연결합니다.
        head 노드는 해당 DB의 파싱 결과로 생성된 모든 노드와 연결
        :return:
        '''

        # 먼저 기존 head 노드 삭제
        query = "MATCH (h:Head) DETACH DELETE h"
        self.neo4j.do_query(query)

        # 최신 Log 노드 가져오기 및 head 노드 생성
        query = f"""
        MATCH (l:Log)
        ORDER BY toInteger(l.revision) DESC LIMIT 1
        CREATE (h:Head {'{'}created_at: datetime(), revision: l.revision, local_path: '{self.local_path}'{'}'})
        MERGE (h)-[:log]->(l)
        RETURN h
        """
        result = self.neo4j.do_query(query)
        head = result[0]['h'] if result else None

        # 최신 FileDiff 노드 가져오기 및 연결
        query = """
        MATCH (f:FileDiff)
        WITH f.file_path AS file_path, f
        ORDER BY file_path, toInteger(f.revision) DESC
        WITH file_path, collect(f)[0] AS latest_filediff
        MATCH (h:Head)
        MERGE (h)-[:head_file_diff]->(latest_filediff)
        """
        self.neo4j.do_query(query)
        # result =
        # latest_filediff = [r['latest_filediff'] for r in self.neo4j.do_query(query)]

        # relations = [ Relationship(head, 'head_file', file_diff) for file_diff in latest_filediff]
        # self.neo4j.

        # 단순 파싱이 아닌 가장 최신 연결 정보를 가진 RvInfo와 연결 정보를 구함
        query = """
        MATCH (r:RvInfo)
        WITH r.src_name AS src_name, r.file_path AS file_path, r
        ORDER BY src_name, toInteger(r.revision) DESC
        WITH src_name, file_path, collect(r)[0] AS latest_rv_info
        MATCH (latest_rv_info)-[rel]-()
        WHERE type(rel) <> 'has'
        RETURN latest_rv_info, type(rel)
        """
        result = self.neo4j.do_query(query)
        relations = []
        for record in result:
            latest_rv_info = record['latest_rv_info']
            rel = record['type(rel)']


            if rel == "delete":
                # relations.append(Relationship(head, "deleted_head_info", latest_rv_info))
                continue
            else:
                relations.append(Relationship(head, "head_info", latest_rv_info, revision = latest_rv_info['revision'], action = rel))
        tx = self.neo4j.graph.begin()
        for rel in relations:
            tx.create(rel)
        tx.commit()

        print(f"최신 relations 노드 개수: {len(relations)}")





    # def create_improved_modify_relationship(self, before_node, next_node):
    #     """
    #     더 나은 modify 관계를 생성합니다. (by agent)
    #     """
    #     # 1. 먼저 두 노드가 같은 함수/메소드인지 확인
    #     if before_node['src_name'] != next_node['src_name']:
    #         return None
    #
    #     # 2. 코드 변경이 있는지 확인
    #     if before_node['code'] == next_node['code']:
    #         return None
    #
    #     # 3. 차이점 계산
    #     import difflib
    #     diff = list(difflib.unified_diff(
    #         before_node['code'].splitlines(),
    #         next_node['code'].splitlines()
    #     ))
    #
    #     lines_added = sum(1 for line in diff if line.startswith('+'))
    #     lines_removed = sum(1 for line in diff if line.startswith('-'))
    #
    #     # 4. 메인 엔티티 노드 가져오기 또는 생성하기 (처음 방문 시)
    #     entity_query = """
    #     MERGE (entity:{label} {{name: $name}})
    #     RETURN entity
    #     """.format(label=before_node.labels.__iter__().__next__())
    #
    #     entity = self.neo4j.graph.run(entity_query, {
    #         "name": before_node['src_name']
    #     }).data()[0]['entity']
    #
    #     # 5. 버전 노드 생성 또는 가져오기
    #     version_query = """
    #     MERGE (version:{label}Version {{
    #         entity_id: $entity_id,
    #         revision: $revision,
    #         file_path: $file_path
    #     }})
    #     ON CREATE SET version.code = $code
    #     RETURN version
    #     """.format(label=before_node.labels.__iter__().__next__())
    #
    #     before_version = self.neo4j.graph.run(version_query, {
    #         "entity_id": entity.identity,
    #         "revision": before_node['revision'],
    #         "file_path": before_node['file_path'],
    #         "code": before_node['code']
    #     }).data()[0]['version']
    #
    #     next_version = self.neo4j.graph.run(version_query, {
    #         "entity_id": entity.identity,
    #         "revision": next_node['revision'],
    #         "file_path": next_node['file_path'],
    #         "code": next_node['code']
    #     }).data()[0]['version']
    #
    #     # 6. Entity와 Version 사이의 관계 생성
    #     self.neo4j.graph.create(Relationship(entity, "HAS_VERSION", before_version))
    #     self.neo4j.graph.create(Relationship(entity, "HAS_VERSION", next_version))
    #
    #     # 7. 버전 간의 modify 관계 생성
    #     modify_rel = Relationship(before_version, "MODIFIES", next_version)
    #     modify_rel['lines_added'] = lines_added
    #     modify_rel['lines_removed'] = lines_removed
    #     modify_rel['change_type'] = "UPDATE"
    #
    #     return self.neo4j.graph.create(modify_rel)


    def update_trace(self):
        '''
        headRV 부터 repo RV 까지 업데이트를 진행합니다.
        https://github.com/thom17/SVNTrace/issues/4
        '''
        head_rv = self.get_head_revision()
        local_rv =SVNManager.get_current_revision(self.local_path)
        if head_rv is None:
            head_rv = local_rv
        repo_rv = SVNManager.get_head_revision(self.repo_path)

        #head rv는 update 되지 않고 local 만 update 처리 된경우
        if int(head_rv) < int(local_rv):
            rv = int(head_rv) #head rv 부터 시작
        else:
            rv = int(local_rv)

        #먼저 로컬 파일 업데이트 및 파싱
        while rv < int(repo_rv):
            self.update_revision(rv)
            rv += 1

        #모든 리비전 업데이트 후 관계 재설정
        self.reconnect_trace_relationship()
        # 마지막으로 head 노드 갱신
        self.connect_head_info()





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