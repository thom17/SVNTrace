from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional
import uvicorn  # 로컬 테스트 실행을 위한 추가

# 기존의 임시 Neo4jConnector 클래스는 제거하고 실제 커넥터를 사용
from fast_api_app.neo4jconnertor import Neo4jConnector  # 주의: 파일명 철자(neo4jconnertor.py)

app = FastAPI()
templates = Jinja2Templates(directory=str((Path(__file__).parent / "templates").resolve()))
connector = Neo4jConnector()

def get_active_db_name() -> Optional[str]:
    if connector.active_db is None:
        return None
    for name, h in connector.db_map.items():
        if h is connector.active_db:
            return name
    # 객체 비교가 실패하면 handler에 database 속성이 있으면 사용
    db = connector.active_db
    name_attr = getattr(db, "database", None)
    return name_attr or None

# 기존 데코레이터(@app.get("/")) 제거하고, 핸들러만 정의
async def root(request: Request):
    # index.html 대신 login.html 렌더링
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/neo4j_login")
async def neo4j_login(request: Request):
    form = await request.form()
    # 폼 값이 비어있으면 커넥터의 기본값 사용
    uri = form.get("uri") or connector.uri
    user = form.get("user") or connector.user
    password = form.get("password") or connector.password

    # 자격 증명 반영 후 로그인
    connector.uri = uri
    connector.user = user
    connector.password = password
    try:
        connector.login()  # 내부에서 db_map 초기화
    except Exception as e:
        return JSONResponse({"success": False, "message": f"로그인 실패: {e}"})

    # DB 목록 및 통계 생성
    dbs = []
    for name, handler in connector.db_map.items():
        dbs.append({
            "name": name,
            # 변경: connector 메서드 -> handler 인스턴스 메서드 호출
            "last_modified": handler.get_last_modified(),
            "node_count": handler.get_node_count(),
        })

    active_db = get_active_db_name() or (dbs[0]["name"] if dbs else None)
    # active_db 객체가 없으면 첫 번째 DB를 활성화해 둠
    if active_db and (connector.active_db is None or connector.db_map.get(active_db) is not connector.active_db):
        connector.active_db = connector.db_map.get(active_db)

    return JSONResponse({
        "success": True,
        "dbs": dbs,
        "active_db": active_db
    })

@app.post("/neo4j_set_active_db")
async def neo4j_set_active_db(request: Request):
    form = await request.form()
    db_name = form.get("db_name")
    if not db_name:
        return JSONResponse({"success": False, "message": "DB명이 필요합니다."})
    target = connector.db_map.get(db_name)
    if not target:
        return JSONResponse({"success": False, "message": "존재하지 않는 DB입니다."})
    connector.active_db = target
    return JSONResponse({"success": True, "active_db": db_name})

if __name__ == "__main__":
    # 포트 충돌/권한 문제 대응: 환경 변수로 우선 지정, 실패 시 가용 포트 자동 탐색
    import os, socket

    def _port_in_use(host: str, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            return s.connect_ex((host, port)) == 0

    def _find_free_port(host: str, start: int = 8000, end: int = 8100) -> int:
        for p in range(start, end + 1):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind((host, p))
                    return p
                except OSError:
                    continue
        return start  # 폴백

    host = os.getenv("APP_HOST", "127.0.0.1")
    try:
        port = int(os.getenv("APP_PORT", "8000"))
    except ValueError:
        port = 8000

    # 여기서만 “/” 라우트를 등록 => login.py를 직접 실행할 때만 적용됨
    app.add_api_route("/", root, response_class=HTMLResponse)

    try:
        # 지정 포트가 사용 중이면 다른 포트로 자동 전환
        if _port_in_use(host, port):
            port = _find_free_port(host, start=port, end=port + 100)
        uvicorn.run(app, host=host, port=port, log_level="info")
    except OSError:
        # 권한/바인딩 오류 시 0.0.0.0로 재시도 + 가용 포트 탐색
        host = "0.0.0.0"
        port = _find_free_port(host, start=8000, end=8100)
        uvicorn.run(app, host=host, port=port, log_level="info")
