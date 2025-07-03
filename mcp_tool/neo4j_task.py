import sys
import json

sys.path.append(r'D:\dev\Python\SVNTrace\SVNTraceAddRVOMS') #현제 경로

from mcp_tool.task_db import TaskDB

sys.path.append(r'D:\dev\python_pure_projects\PyUtil')

from neo4j_manager.neo4jHandler import Neo4jHandler
from mcp.server.fastmcp import FastMCP

from py2neo import Graph, Node, Relationship

URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "123456789"

neo4j_handler = Neo4jHandler("bolt://localhost:7687", "neo4j", "123456789", "test")

taskDB = TaskDB()
mcp = FastMCP("taskDB")


@mcp.tool()
def make_head_filters_task(task_str: str) -> str:
    """
    헤더 필터링 작업을 생성합니다.
    :param task_str: 작업 문자열
    :return: 작업 ID
    """

    main_id = taskDB.create_main_task(task_str)

    query = f'''
    MATCH (n:Head)-[r:head_info]-(info: RvFunctionInfo)
    return info'''
    result = neo4j_handler.graph.run(query)
    records = [dict(record['info']) for record in result]

    list_sub_task_str = []
    for record in records:
        list_sub_task_str.append(f"{task_str}  : {str(record)}")
    taskDB.create_sub_tasks(main_id, list_sub_task_str)

    return f"작업이 생성되었습니다. ID: {main_id}, 작업 수: {len(list_sub_task_str)}"

@mcp.tool()
def solve_sub_task(task_id: int, answer: str) -> str:
    """
    서브 작업을 해결합니다.
    :param task_id: 작업 ID
    :param answer: 답변 (Yes or No)
    :return: 결과 메시지
    """

    taskDB.update_sub_task(task_id, answer)
    after_tasks = taskDB.fetch_pending_sub_tasks()

    return f'{len(after_tasks)} 개의 서브 작업이 남아 있습니다.'

@mcp.tool()
def get_task():
    """
    현재 처리 안된 서브 작업 하나를 조회합니다.
    :return: 작업 목록
    """
    tasks = taskDB.fetch_pending_sub_tasks()[0]
    return json.dumps(tasks, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    # print(make_head_filters_task("이 메서드는 메모라 누수가 발생하나요?"))
    print(get_task())
    print(solve_sub_task(2, "Yes"))

