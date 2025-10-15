# fast_api/tuto.py
#
# import clang.cindex
# try:
#     clang.cindex.Config.set_library_file(r"C:\Program Files\LLVM\bin\libclang.dll")
#     print('libclang.dll 설정 성공')
# except Exception as e:
#     print("libclang.dll 설정 실패")
#     print(e)

#
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import svn_managers.svn_manager as SVNManager
from svn_managers.svn_data import Log, FileDiff
from neo4j_manager.neo4jHandler import Neo4jHandler, Node
from clangParser.datas.CUnit import CUnit
import oms.Mapper as OMSMapper
import os
from svn_oms.dataset.svn_oms import RvUnit
from svn_oms.dataset.rv_info_factory import info2Rvinfo, dict2RvUnit
from pathlib import Path

app = FastAPI()
# templates = Jinja2Templates(directory="templates")
# templates = Jinja2Templates(directory="fast_api_app/templates")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

class SVNLogViewer:
    def __init__(self):
        self.search_path = None
        self.search_datas = None
        self.neo4j: Neo4jHandler = self.connect_db()

    def connect_db(self):
        try:
            uri = "bolt://localhost:7687"
            user = "neo4j"
            password = "123456789"
            database = "merge"
            return Neo4jHandler(uri=uri, user=user, password=password, database=database)
        except Exception as e:
            print(f"Failed to connect to database: {e}")
            return None

    def get_preview_texts(self, log: Log, file_diffs: list[FileDiff]) -> tuple[str, str]:
        msg = log.msg.split('\n')[0] if log.msg and '\n' in log.msg else (log.msg or "")
        filenames = [os.path.basename(diff.file_path) for diff in file_diffs]
        return msg, ", ".join(filenames)

    def save_db(self):
        print('before save_db ', len(self.search_datas))
        self.neo4j.print_info()
        save_datas = []
        save_relations = []
        for log, filediffs in self.search_datas.values():
            save_datas.append(log)
            save_datas.extend(filediffs)
            for filediff in filediffs:
                save_relations.append((log, filediff, 'file_diff'))
        self.neo4j.save_data(save_datas)
        self.neo4j.add_relationship(save_relations)
        print('after save_db ', len(self.search_datas))
        self.neo4j.print_info()

    def parse_for_rvinfo(self, cunit: CUnit, revision: str):
        rvinfos = []
        print('parse_for_rvinfo', cunit.file_path)
        for cursor in cunit.get_this_Cursor():
            info = OMSMapper.Cursor2InfoBase(cursor)
            if info:
                rvinfos.append(info2Rvinfo(revision, info))
        return rvinfos

    def parse_data(self):
        def __load_rv_unit(file_diff: FileDiff):
            path = file_diff.file_path.replace('\\', '\\\\')
            rv = file_diff.revision
            query = f"MATCH (unit:RvUnit) WHERE unit.revision = '{rv}' AND unit.file_path = '{path}' RETURN unit"
            result = self.neo4j.do_query(query)
            if not result:
                return None
            elif len(result) == 1:
                node: Node = result[0]['unit']
                unit = dict2RvUnit(dict(node))
            else:
                raise Exception(f"Multiple nodes found for revision {rv} and file {path} {len(result)}")
            return unit

        print('1. check to parse files')
        to_parse_files = []
        for log, file_diffs in self.search_datas.values():
            for diff in file_diffs:
                file_path: str = diff.file_path
                if file_path.endswith('.cpp') or file_path.endswith('.h'):
                    to_parse_files.append(diff)
                    SVNManager.do_update(file_path, log.revision)

        print('2. parse/load files')
        to_save_datas = []
        to_add_relations = []
        rv_units = []
        for file_diff in to_parse_files:
            if __load_rv_unit(file_diff) is None:
                unit = CUnit.parse(file_path=file_diff.file_path)
                unit = RvUnit(unit, file_diff.revision)
                rv_units.append(unit)
                to_save_datas.append(unit)
            else:
                print('load_rv_unit ', file_diff.file_path)

        print('2.1 parse rvinfo')
        for rvunit in rv_units:
            rv_infos = self.parse_for_rvinfo(rvunit.cunit, rvunit.revision)
            to_save_datas.extend(rv_infos)
            for rvinfo in rv_infos:
                to_add_relations.append((rvunit, rvinfo, 'has'))

        print('3. save db')
        print('before save_db ', len(to_save_datas), '/', len(to_add_relations))
        self.neo4j.print_info()
        self.neo4j.save_data(to_save_datas)
        self.neo4j.add_relationship(to_add_relations)
        print('after save_db ', len(to_save_datas), '/', len(to_add_relations))
        self.neo4j.print_info()

viewer = SVNLogViewer()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/", response_class=HTMLResponse)
async def post_index(
    request: Request,
    path: str = Form(...),
    query_type: str = Form("recent"),
    count: int = Form(50),
    start_revision: str = Form(None),
    end_revision: str = Form(None)
):
    search_params = {
        "path": path,
        "query_type": query_type,
        "count": count,
        "start_revision": start_revision,
        "end_revision": end_revision
    }
    logs = None
    log_error = None
    try:
        if query_type == "recent":
            logs_map = SVNManager.get_recent_logs(path, count)
        else:
            if not end_revision:
                end_revision = SVNManager.get_current_revision(path)
            logs_map = SVNManager.get_svn_range_log_dif(path, start_revision, end_revision)
        viewer.search_datas = logs_map
        search_params["revisions_found"] = len(logs_map)
        logs = []
        for revision, (log, file_diffs) in logs_map.items():
            preview_msg, preview_path = viewer.get_preview_texts(log, file_diffs)
            logs.append((revision, {
                "log": log,
                "file_diffs": file_diffs,
                "preview_msg": preview_msg,
                "preview_path": preview_path
            }))
        logs.sort(key=lambda x: int(x[0]), reverse=True)
    except Exception as e:
        log_error = f"로그를 가져오는 중 오류 발생: {e}"

    return templates.TemplateResponse("index.html", {
        "request": request,
        "logs": logs,
        "log_error": log_error,
        "search_params": search_params
    })

@app.post("/save_db")
async def save_db():
    try:
        viewer.save_db()
        return JSONResponse({"message": "Database saved successfully"})
    except Exception as e:
        return JSONResponse({"message": f"Error saving database: {str(e)}"}, status_code=500)

@app.post("/parse_data")
async def parse_data():
    try:
        viewer.parse_data()
        return JSONResponse({"message": "Data parsed successfully"})
    except Exception as e:
        return JSONResponse({"message": f"Error parsing data: {str(e)}"}, status_code=500)

if __name__ == "__main__":
    # python tuto.py 로 직접 실행할 때 Uvicorn으로 FastAPI 앱을 기동합니다.
    try:
        import uvicorn
    except ImportError:
        print("uvicorn 패키지가 설치되어 있지 않습니다. 다음으로 설치 후 다시 실행하세요: pip install uvicorn[standard]")
        raise

    import socket
    host = "127.0.0.1"

    def _find_open_port(start_port: int, attempts: int = 20) -> int:
        base = start_port
        for off in range(attempts):
            cand = base + off
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind((host, cand))
                    # 바인딩 성공 확인 후 즉시 해제하여 uvicorn이 사용할 수 있게 함
                    return cand
                except OSError:
                    continue
        return base

    try:
        base_port = int(os.getenv("PORT", "8000"))
    except ValueError:
        base_port = 8000

    port = _find_open_port(base_port)
    if port != base_port:
        print(f"기본 포트 {base_port} 사용 불가. 대체 포트 {port}로 기동합니다.")

    # reload는 인스턴스 전달 방식에선 비권장이라 기본 False로 둡니다.
    uvicorn.run(app, host=host, port=port)
