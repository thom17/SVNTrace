# SVNTrace

SVN 프로젝트의 버전별 코드를 파싱하여 메서드/변수 단위로 Neo4j 그래프 DB에 저장하고, MCP 도구와 웹 UI를 통해 조회할 수 있는 통합 도구입니다.

## 핵심 차별점

Git/SVN의 **파일 단위 변경 추적**을 넘어, **메서드 단위 수정 이력 추적**을 제공합니다.

특정 메서드가 언제, 어떻게 변경되었는지를 리비전별로 추적하고, 메서드 간 관계를 그래프로 시각화할 수 있습니다.

## 현재 아키텍처

동작하는 핵심 흐름은 다음과 같습니다:

```
trace_manager.py → maindb.py (TraceDataBase)
     │                    │
     │                    ├── PyUtil/neo4j_manager  (Neo4j 저장)
     │                    ├── PyUtil/svn_managers    (SVN 조회/업데이트)
     │                    ├── ClangParser/CUnit      (C++ AST 파싱)
     │                    └── svn_oms/dataset/        (데이터 모델)
     │
mcp_tool/neo4j_server.py → Neo4j DB (MCP 도구로 Agent에게 조회 제공)
fast_api_app/             → maindb.py → Neo4j DB (웹 UI)
```

### 주요 컴포넌트

- **trace_manager.py**: SVN 저장소 업데이트 및 파싱 프로세스 관리
- **maindb.py (TraceDataBase)**: 핵심 엔진. SVN 데이터를 파싱하여 Neo4j에 저장하고 관계를 연결
- **mcp_tool/neo4j_server.py**: MCP 서버로 AI Agent에게 12개 조회 도구 제공
- **fast_api_app/**: 웹 기반 DB 관리 대시보드

## 디렉토리 구조

| 디렉토리 | 역할 | 상태 |
|---|---|---|
| `neo4j_svntrace/` | 핵심 엔진. TraceDataBase — SVN→파싱→Neo4j 저장→관계 연결 | ✅ 메인 |
| `svn_oms/dataset/` | 데이터 모델 (RvUnit, RvInfoBase, RvClassInfo 등) | ✅ 사용 중 |
| `mcp_tool/` | MCP 서버 — Neo4j 기반 12개 도구 제공 | ✅ 사용 중 |
| `fast_api_app/` | FastAPI 웹 UI — DB 관리 대시보드 | ✅ 사용 중 |
| `test/` | 테스트 코드 | 참고용 |
| `_legacy/` | 이전 버전 코드 (parser.py, parser2.py, db_handler.py, flask_app 등) | 📦 아카이브 |

### 활성 코드 구조

```
svn_oms/
  ├── __init__.py
  └── dataset/
      ├── __init__.py
      ├── svn_oms.py          ← RvUnit, RvInfoBase 등 (현재 사용 중)
      └── rv_info_factory.py  ← info2Rvinfo, from_parsing 등 (현재 사용 중)
```

## 의존성

### Python 패키지

- **PyUtil**: Neo4j 핸들러, SVN 매니저 등 유틸리티 (Git 의존성)
- **ClangParserProject**: C++ 코드 AST 파싱 (Git 의존성)
- Python 3.10+

설치:

```bash
pip install -r requirements.txt
```

`requirements.txt`는 다음 Git 의존성을 포함합니다:
```
git+https://github.com/thom17/PyUtil.git
git+https://github.com/thom17/ClangParserProject.git
```

### 외부 서비스

- **Neo4j**: 그래프 데이터베이스 (로컬 `bolt://localhost:7687`)
  - 사용자: neo4j
  - 기본 DB: test

## Neo4j 그래프 스키마

### 노드 타입

- **Log**: SVN 커밋 로그 정보 (revision, author, date, message)
- **FileDiff**: 파일 변경 정보 (file_path, revision, status)
- **RvUnit**: 리비전별 파싱 단위 (file_path, revision)
- **RvClassInfo**: 클래스 정보 (src_name, revision, file_path, code)
- **RvFunctionInfo**: 메서드 정보 (src_name, revision, file_path, name, type_str, code)
- **RvVarInfo**: 변수 정보 (src_name, revision, file_path, name, type_str)
- **Head**: 최신 버전 추적을 위한 헤드 노드

### 관계 타입

- **next_log**: Log → Log (다음 리비전)
- **file_diff**: Log → FileDiff (로그의 파일 변경)
- **unit**: FileDiff → RvUnit (파일 변경의 파싱 단위)
- **has**: RvUnit → RvClassInfo/RvFunctionInfo/RvVarInfo (파싱 단위가 포함하는 정보)
- **next_diff**: FileDiff → FileDiff (동일 파일의 다음 변경)
- **modify/add/delete**: FileDiff → RvUnit (변경 타입별 관계)
- **head_info**: Head → RvFunctionInfo/RvClassInfo (최신 버전 정보)
- **head_file_diff**: Head → FileDiff (최신 파일 변경)
- **log**: RvUnit → Log (파싱 단위의 원본 로그)

## MCP 도구

MCP(Model Context Protocol) 서버를 통해 AI Agent가 Neo4j 데이터베이스를 조회할 수 있는 12개 도구를 제공합니다.

### 1. get_all_rvclass_infos
- **설명**: 리비전이 포함된 클래스 노드 정보 조회
- **매개변수**: `keyword` (선택) - 필터링할 키워드
- **반환**: src_name을 key로 하여 revisions를 모아둔 JSON

### 2. get_all_rv_function_infos
- **설명**: 모든 메서드 노드 정보 조회
- **반환**: 메서드 정보 JSON 배열

### 3. get_var_infos
- **설명**: 리비전이 포함된 변수 노드 정보 조회
- **매개변수**: `query` (선택) - Cypher 쿼리
- **반환**: 변수 정보 JSON 배열

### 4. get_recent_logs
- **설명**: SVN 로그 정보를 최근 순으로 조회
- **매개변수**: `keyword` (선택) - 필터링할 키워드
- **반환**: Log 노드 정보 JSON 배열

### 5. get_file_diff
- **설명**: 특정 리비전과 파일 경로에 해당하는 FileDiff 정보 조회
- **매개변수**: 
  - `revision` (필수) - 리비전 번호
  - `file_path` (필수) - 파일 경로
- **반환**: FileDiff 정보 JSON

### 6. get_file_diffs
- **설명**: SVN 파일의 변경 정보 모두 조회
- **매개변수**: `keyword` (선택) - 필터링할 키워드
- **반환**: file_path를 key로 하여 revisions를 모아둔 JSON

### 7. search_rv_function_infos_by_keyword
- **설명**: 키워드가 포함된 메서드 정보 검색
- **매개변수**: `keyword` (필수) - 리비전 번호, 파일 경로, src_name 중 하나 이상
- **반환**: src_name, file_path 쌍을 key로 하여 revision를 모아둔 JSON
- **필드**:
  - `revisions`: 메서드 정보가 파싱된 시점의 리비전
  - `file_path`: 메서드가 위치한 파일 경로
  - `src_name`: 메서드를 식별하기 위한 전체 이름 (클래스+시그니쳐)

### 8. get_rv_fun_info
- **설명**: src_name과 revision으로 특정 RvFunctionInfo 조회
- **매개변수**:
  - `src_name` (필수) - 메서드의 전체 이름
  - `revision` (필수) - 리비전 번호
- **반환**: 메서드 상세 정보 JSON
- **필드**:
  - `revision`: 리비전 번호
  - `file_path`: 파일 경로
  - `src_name`: 메서드 전체 이름
  - `name`: 메서드 단순 이름
  - `type_str`: 반환 타입
  - `code`: 메서드 코드

### 9. get_head_functions
- **설명**: 가장 최신(head)의 메서드 정보 반환
- **반환**: 최신 메서드 정보 JSON 배열
- **필드**:
  - `revision`: 리비전 번호
  - `file_path`: 파일 경로
  - `src_name`: 메서드 전체 이름
  - `name`: 메서드 단순 이름

### 10. search_head_functions_by_keyword
- **설명**: 키워드가 포함된 최신(head) 메서드 정보 검색
- **매개변수**:
  - `keyword` (필수) - 검색 키워드
  - `check_code` (선택) - True 설정 시 code 내부도 검색
- **반환**: 최신 메서드 정보 JSON 배열
- **필드**: get_rv_fun_info와 동일 + code 필드

### 11. do_query
- **설명**: 직접 Cypher 쿼리 실행
- **매개변수**: `query` (필수) - Cypher 쿼리 문자열
- **반환**: 쿼리 결과 JSON

### 12. change_database
- **설명**: 사용할 Neo4j 데이터베이스 변경
- **매개변수**: `dbname` (필수) - 데이터베이스 이름
- **반환**: 성공 시 1

## 사용 방법

### 1. SVN 저장소 파싱 및 Neo4j 저장

```python
from neo4j_svntrace.trace_manager import TraceDataBase

# TraceDataBase 인스턴스 생성
db = TraceDataBase(
    uri="bolt://localhost:7687",
    user="neo4j",
    pwd="your_password",
    dbname="your_database"
)

# SVN 저장소 업데이트 및 파싱
db.update_from_svn(svn_repo_url, start_revision, end_revision)
```

### 2. MCP 서버 실행

```bash
cd mcp_tool
python neo4j_server.py
```

MCP 서버가 실행되면 AI Agent가 12개 도구를 사용하여 Neo4j 데이터베이스를 조회할 수 있습니다.

### 3. 웹 UI 실행

```bash
cd fast_api_app
uvicorn main:app --reload
```

웹 브라우저에서 `http://localhost:8000`으로 접속하여 데이터베이스 관리 대시보드를 사용할 수 있습니다.

## 개발 히스토리

프로젝트는 3세대에 걸쳐 진화했습니다. 이전 버전의 코드는 `_legacy/` 디렉토리에 보관되어 있습니다.

자세한 내용은 [`_legacy/README.md`](_legacy/README.md)를 참조하세요.

## 라이선스

This project is maintained by [thom17](https://github.com/thom17).
