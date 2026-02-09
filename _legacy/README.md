# Legacy Code Archive

이 디렉토리는 SVNTrace 프로젝트의 이전 버전 코드를 보관합니다.

## 파일 목록

### svn_oms/
- **parser.py** - 1세대 파서 (SVNDataSet 기반)
- **parser2.py** - 2세대 파서 (SVNProjectParser 기반)
- **db_handler.py** - 1세대 데이터베이스 핸들러 (DBHandler)
- **dataset/svn_trace_data.py** - 2세대 데이터 모델 (SVNTraceData)

### flask_app/
- Flask 기반 웹 UI (현재 fast_api_app으로 교체됨)

## 진화 과정

SVNTrace 프로젝트는 3세대에 걸쳐 발전했습니다:

### 1세대: 메모리 기반 파싱 (12월 18일경)

**파일**: `parser.py`, `db_handler.py`

**아키텍처**:
```
SVNDataSet (메모리에 데이터 수집)
    ↓
DBHandler (Neo4j 저장)
```

**특징**:
- `SVNDataSet`: 메모리에 (revision, path) → CUnit 데이터를 수집
- 파싱과 저장이 분리되어 있음
- 전체 데이터를 메모리에 로드한 후 일괄 저장

**문제점**:
- 대용량 프로젝트 처리 시 메모리 부족
- 파싱과 저장이 분리되어 있어 중간 단계에서 오류 발생 시 복구 어려움

### 2세대: 프로젝트 단위 파싱 (12월 20일경)

**파일**: `parser2.py`, `svn_trace_data.py`

**아키텍처**:
```
SVNProjectParser (프로젝트 단위 파싱)
    ↓
SVNTraceData (그래프 노드)
    ↓
메모리 내 그래프 구조 → Neo4j 저장
```

**특징**:
- `SVNProjectParser`: start_rv ~ end_rv 범위 지정 가능
- `SVNTraceData`: 그래프 노드 역할
  - next_data: 다음 리비전 링크
  - before_data: 이전 리비전 링크
- 메모리 내에서 그래프 구조를 먼저 구축한 후 DB에 저장

**개선점**:
- 리비전 범위 지정으로 부분 파싱 가능
- 그래프 관계를 명시적으로 표현

**문제점**:
- 여전히 메모리 내 그래프 구조 관리가 복잡
- 대용량 데이터 처리 시 메모리 문제 지속

### 3세대: DB 중심 아키텍처 (현재)

**파일**: `neo4j_svntrace/maindb.py` (TraceDataBase)

**아키텍처**:
```
TraceDataBase
    ↓
리비전별 즉시 파싱 → Neo4j 저장
    ↓
Neo4j Cypher로 관계 재구성
```

**특징**:
- 리비전별로 즉시 파싱하고 Neo4j에 저장
- 메모리 내 그래프 구조 제거
- Cypher 쿼리로 관계를 DB 레벨에서 재구성
- PyUtil/neo4j_manager, PyUtil/svn_managers, ClangParser/CUnit 등 외부 라이브러리 활용

**개선점**:
- 메모리 효율적 - 대용량 프로젝트 처리 가능
- 단순화된 아키텍처 - 복잡한 메모리 관리 제거
- 확장 가능 - DB 중심으로 새로운 쿼리 추가 용이
- 견고성 - 중간 단계 오류 시 복구 가능

## flask_app → fast_api_app

**flask_app**: Flask 기반 초기 웹 UI 시도

**fast_api_app** (현재): FastAPI 기반 웹 대시보드
- 더 나은 API 문서화 (자동 Swagger 생성)
- 비동기 처리 지원
- 타입 힌트 기반 자동 검증

## 테스트 코드 참고사항

`test/` 디렉토리의 일부 테스트 코드는 여전히 레거시 코드를 import합니다:
- `test/parser.py`: `from svn_oms.parser import SVNProjectParser`
- `test/main.py`: `from svn_oms.db_handler import DBHandler`

이 테스트 코드들은 참고용으로 남겨두었으며, 현재 메인 코드베이스와는 독립적으로 동작합니다.

레거시 코드를 사용하는 테스트를 실행하려면:
```python
# 임포트 경로 수정 필요
from _legacy.svn_oms.parser import SVNProjectParser
from _legacy.svn_oms.db_handler import DBHandler
```

## 보존 이유

이 레거시 코드들은 다음 이유로 보관됩니다:

1. **학습 자료**: 프로젝트 진화 과정을 이해하는 데 도움
2. **참고 구현**: 특정 기능의 이전 구현 방식 참고
3. **백업**: 혹시 모를 롤백 시나리오 대비

## 사용 금지

**현재 프로젝트의 메인 코드에서는 이 레거시 코드를 import하지 않습니다.**

새로운 코드 작성 시 반드시 다음을 사용하세요:
- `neo4j_svntrace/maindb.py` (TraceDataBase)
- `svn_oms/dataset/svn_oms.py` (RvUnit, RvInfoBase 등)
- `svn_oms/dataset/rv_info_factory.py` (info2Rvinfo, from_parsing 등)
