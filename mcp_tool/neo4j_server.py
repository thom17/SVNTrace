import sys
import json

# from mcp_tuto.clang_server import driver

sys.path.append(r'D:\dev\python_pure_projects\PyUtil')

from neo4j_manager.neo4jHandler import Neo4jHandler
from mcp.server.fastmcp import FastMCP

from py2neo import Graph, Node, Relationship

URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "123456789"

neo4j_handler = Neo4jHandler("bolt://localhost:7687", "neo4j", "123456789", "test")
mcp = FastMCP("neo4j")

def add_connect_test_data():
    '''tool을 사용할때마다 전체 코드가 사용되는지 확인하기 위해'''
    from datetime import datetime
    current_time = datetime.now().strftime("%H:%M:%S")

    from dataclasses import dataclass
    @dataclass
    class ConnectTest:
        time: str

    neo4j_handler.save_data(ConnectTest(current_time))
add_connect_test_data()

@mcp.tool()
def get_all_rvclass_infos(keyword : str = None) -> str:
    '''Neo4j 데이터베이스에서 리비전이 포함된 클래스 노드의 정보를 모두 조회합니다.
    src_name을 key로 하여 revisions를 모아둠
    keyword를 입력받아 해당 키워드가 포함된 클래스 노드만 조회합니다.
    '''
    if keyword:
        query = f"""MATCH (n:RvClassInfo)
WHERE toLower(n.src_name) CONTAINS '{keyword.lower()}'
RETURN n.src_name, collect(n.revision) AS revisions
"""
    else:
        query = """
MATCH (n:RvClassInfo)
RETURN  n.src_name, collect(n.revision) AS revisions
"""
    result = neo4j_handler.graph.run(query)
    records = [dict(record) for record in result]
    return json.dumps(records, ensure_ascii=False, indent=2)

@mcp.tool()
def get_all_rv_function_infos() -> str:
    '''
    Neo4j 데이터베이스에서 리비전이 포함된 메서드 노드의 정보를 모두 조회합니다.
    이 함수는 파라미터를 받지 않으며 항상 같은 쿼리를 실행합니다.
    src_name, file_path 쌍을 key로 하여 revision를 모아둠

    revisions : str 해당 메서드의 정보가 파싱된 시점의 리비전 (주의: 문자열 타입의 숫자)
    file_path : str 해당 메서드 정보가 위치한 파일 경로
    src_name : str 해당 메서드를 식별하기 위한 전체적인 이름 ( 클래스+시그니쳐)
    '''
    query = """
MATCH (n:RvFunctionInfo)
RETURN 
n.src_name AS src_name, n.file_path AS file_path, 
collect(n.revision) AS revisions
"""
    result = neo4j_handler.graph.run(query)
    records = [dict(record) for record in result]
    return json.dumps(records, ensure_ascii=False, indent=2)

@mcp.tool()
def get_var_infos(query : str = "MATCH (n:RvVarInfo) RETURN n") -> str:
    '''Neo4j 데이터베이스에서 리비전이 포함된 변수 노드의 정보를 모두 조회합니다.
    default = "MATCH (n:RvVarInfo) RETURN n"
    각 RvVarInfo는 다음과 같은 속성을 가짐
    revision : str 해당 변수의 정보가 파싱된 시점의 리비전 (주의: 문자열 타입의 숫자)
    code : str 해당 리비전에 해당하는 코드
    file_path : str 해당 변수 정보가 위치한 파일 경로
    name : str 해당 변수의 이름
    src_name : str 해당 변수를 식별하기 위한 전체적인 이름 ( 클래스/메서드+변수이름)
    '''
    result = neo4j_handler.graph.run(query)
    records = [dict(record) for record in result]
    return json.dumps(records, ensure_ascii=False, indent=2)

@mcp.tool()
def get_recent_logs(keyword : str = None) -> str:
    '''Neo4j 데이터베이스에서 SVN LOG 정보를 최근 순으로 모두 조회합니다.
    각 Log 다음과 같은 속성을 가짐
    revision : str 해당하는 커밋 리비전 (주의: 문자열 타입의 숫자)
    author : str 해당 리비전을 수정한 저자
    msg : str 해당 리비전의 커밋 메시지
    data : str 해당 리비전의 커밋 날짜 ex("2024-03-26T23:46:50.495192000")
    '''
    if keyword:
        query = f'''MATCH (n:Log)
WHERE toLower(n.msg) CONTAINS '{keyword.lower()}'
RETURN n.revision as revision, n.msg as msg'''
    else:
        query = '''MATCH (n:Log) RETURN n.revision as revision, n.msg as msg'''
    result = neo4j_handler.graph.run(query)
    records = [dict(record) for record in result]
    return json.dumps(records, ensure_ascii=False, indent=2)

@mcp.tool()
def get_file_diff(revision: str, file_path: str) -> str:
    '''Neo4j 데이터베이스에서 특정 리비전과 파일 경로에 해당하는 FileDiff 정보를 조회합니다.
    revision : str 해당 리비전의 파일 변경 정보가 파싱된 시점의 리비전 (주의: 문자열 타입의 숫자)
    file_path : str 해당 파일의 경로
    '''
    query = f'''
MATCH (n:FileDiff)
WHERE n.revision = "{revision}" AND n.file_path CONTAINS "{file_path}"
RETURN n.revision, n.file_path, n.action
'''
    result = neo4j_handler.graph.run(query)
    records = [dict(record) for record in result]
    return json.dumps(records, ensure_ascii=False, indent=2)

@mcp.tool()
def get_file_diffs(keyword : str = None) -> str:
    '''Neo4j 데이터베이스에서 SVN 파일의 변경 정보를 모두 조회합니다.
    keyword를 입력받아 해당 키워드가 포함된 파일 경로의 변경 정보만 조회합니다.
    각 FileDiff는 다음과 같은 속성을 가짐
    revision : str 해당 리비전의 파일 변경 정보가 파싱된 시점의 리비전 (주의: 문자열 타입의 숫자)
    file_path : str 해당 파일의 경로
    action : str 해당 리비전에 해당하는 파일의 변경 동작 (Add, Modified, Delete)
    '''
    if keyword:
        query = f'''
MATCH (n:FileDiff)
WHERE toLower(n.file_path) CONTAINS "{keyword.lower()}"
RETURN n.file_path, collect(n.revision) AS revisions'''
    else:
        query = '''MATCH (n:FileDiff) RETURN n.file_path, collect(n.revision) AS revisions'''
    result = neo4j_handler.graph.run(query)
    records = [dict(record) for record in result]
    return json.dumps(records, ensure_ascii=False, indent=2)

@mcp.tool()
def search_rv_function_infos_by_keyword(keyword: str):
    '''
    키워드가 포함된 search_rv_function_infos
    keyword는 리비전 번호, 파일 경로, src_name 중 한개 이상 포함되어야 합니다.
    src_name, file_path 쌍을 key로 하여 revision를 모아둠

    revisions : str 해당 메서드의 정보가 파싱된 시점의 리비전 (주의: 문자열 타입의 숫자)
    file_path : str 해당 메서드 정보가 위치한 파일 경로
    src_name : str 해당 메서드를 식별하기 위한 전체적인 이름 ( 클래스+시그니쳐)
    '''
    query = """
    MATCH (n:RvFunctionInfo)
    RETURN 
    n.src_name AS src_name, n.file_path AS file_path, 
    collect(n.revision) AS revisions
    """
    result = neo4j_handler.graph.run(query)
    records = []
    keyword = keyword.lower()
    for r in result:
        if keyword in r['src_name'].lower() or keyword in r['file_path'].lower()  or keyword in r['revisions']:
            records.append(dict(r))

    return json.dumps(records, ensure_ascii=False, indent=2)


@mcp.tool()
def get_rv_fun_info(src_name: str, revision: str):
    '''
    src_name과 revision으로 특정 RvFunctionInfo 를 찾는 메서드
    revisions : str 해당 메서드의 정보가 파싱된 시점의 리비전 (주의: 문자열 타입의 숫자)
    file_path : str 해당 메서드 정보가 위치한 파일 경로
    src_name : str 해당 메서드를 식별하기 위한 전체적인 이름 ( 클래스+시그니쳐)
    name : str 메서드의 단순 이름
    type_str : str 반환 타입
    code : 메서드 코드 정보

    '''
    query = f'''
        MATCH (n:RvFunctionInfo)
        WHERE n.src_name = "{src_name}" AND n.revision = "{revision}"
        RETURN n
        '''
    result = neo4j_handler.graph.run(query)
    records = [dict(record['n']) for record in result]
    return json.dumps(records, ensure_ascii=False, indent=2)

@mcp.tool()
def get_head_functions():
    '''
    가장 최신(head)의 메서드 정보(RvFunctionInfos)를 반환한다.
    revisions : str 해당 메서드의 정보가 파싱된 시점의 리비전 (주의: 문자열 타입의 숫자)
    file_path : str 해당 메서드 정보가 위치한 파일 경로
    src_name : str 해당 메서드를 식별하기 위한 전체적인 이름 ( 클래스+시그니쳐)
    name : str 메서드의 단순 이름
    type_str : str 반환 타입
    code : 메서드 코드 정보
    '''
    query = f'''
MATCH (n:Head)-[r:head_info]-(info: RvFunctionInfo)
return info'''
    result = neo4j_handler.graph.run(query)
    records = [dict(record['info']) for record in result]
    return json.dumps(records, ensure_ascii=False, indent=2)

@mcp.tool()
def search_head_functions_by_keyword(keyword : str, check_code: bool = False):
    '''
    가장 최신(head)의 메서드 정보(RvFunctionInfos)를 반환한다. (keyword 를 포함하는)
    파라미터로 check_code 를 True로 설정하면 code 내부도 키워드로 검색한다.
    revisions : str 해당 메서드의 정보가 파싱된 시점의 리비전 (주의: 문자열 타입의 숫자)
    file_path : str 해당 메서드 정보가 위치한 파일 경로
    src_name : str 해당 메서드를 식별하기 위한 전체적인 이름 ( 클래스+시그니쳐)
    name : str 메서드의 단순 이름
    type_str : str 반환 타입
    code : 메서드 코드 정보
    '''
    if check_code:
        query = f'''
MATCH (n:Head)-[r:head_info]-(info: RvFunctionInfo)
WHERE lower(info.code) CONTAINS "{keyword.lower()}" OR info.revision = "{keyword}"
return info'''
    else:
        query = f'''
MATCH (n:Head)-[r:head_info]-(info: RvFunctionInfo)
WHERE lower(info.src_name) CONTAINS "{keyword.lower()}" OR info.revision = "{keyword}"
return info'''
    result = neo4j_handler.graph.run(query)
    records = [dict(record['info']) for record in result]
    return json.dumps(records, ensure_ascii=False, indent=2)



@mcp.tool()
def do_query(query : str) -> str:
    '''query를 입력받아 실행'''
    result = neo4j_handler.graph.run(query)
    records = [dict(record) for record in result]
    return json.dumps(records, ensure_ascii=False, indent=2)

@mcp.tool()
def change_database(dbname: str) -> int:
    '''db name을 입력받아 db를 변경'''
    neo4j_handler.change_database(dbname)
    return 1


if __name__ == "__main__":
    # print(search_rv_function_infos_by_keyword('8400'))
    # print(get_rv_fun_info("CActuatorHybridFixture._transparentDrillHoleModel()", 8357))
    print(search_head_functions_by_keyword("->", True))


