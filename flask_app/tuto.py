from flask import Flask, request, render_template_string, jsonify
import svn_manager.svn_manager as SVNManager
from svn_manager.svn_data import Log, FileDiff

from neo4j_manager.neo4jHandler import Neo4jHandler, Node

from clangParser.datas.CUnit import CUnit, Cursor
# from oms.dataset.info_factory import cursor2info
import oms.Mapper as OMSMapper

import os

from svn_oms.dataset.svn_oms import RvUnit

from svn_oms.dataset.rv_info_factory import info2Rvinfo, dict2RvUnit

class SVNLogViewer:
    def __init__(self):
        self.app = Flask(__name__)
        self._configure_routes()
        self.search_path = None
        self.search_datas = None

        self.neo4j: Neo4jHandler = self.connect_db()

    def connect_db(self):
        '''
        db 재연결. 추후 DB 관련 기능이 많이 개발 되면 추가 구현.
        2025-03-31 기준 현제는 초기화 함수
        '''

        # 추후 UI로 부터 입력값 받기
        try:
            from neo4j_manager.neo4jHandler import Neo4jHandler
            uri = "bolt://localhost:7687"
            user = "neo4j"
            password = "123456789"
            database = "merge"
            return Neo4jHandler(uri=uri, user=user, password=password, database=database)
        except Exception as e:
            print(f"Failed to connect to database: {e}")
            return None

    def _configure_routes(self):
        self.app.route('/', methods=['GET', 'POST'])(self.index)
        self.app.route('/save_db', methods=['POST'])(self.save_db_route)
        self.app.route('/parse_data', methods=['POST'])(self.parse_data_route)

    def get_preview_texts(self, log: Log, file_diffs: list[FileDiff]) -> tuple[str, str]:
        # Get first line of commit message
        msg = ""
        if log.msg and '\n' in log.msg:
            msg = log.msg.split('\n')[0]
        else:
            msg = log.msg or ""

        # Get filenames without paths
        filenames = [os.path.basename(diff.file_path) for diff in file_diffs]
        return msg, ", ".join(filenames)

    def save_db(self):
        """
        Save the SVN logs to a database.
        """
        # Placeholder for database save logic
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
        """
        CUnit을 파싱하여 RVInfo 정보를 추출합니다.
        Parse the unit for RV information.
        """
        rvinfos = []
        print('parse_for_rvinfo', cunit.file_path)
        for cursor in cunit.get_this_Cursor():
            info = OMSMapper.Cursor2InfoBase(cursor)
            if info:
                rvinfos.append( info2Rvinfo(revision, info))
        return rvinfos


    def parse_data(self):
        """
        Parse SVN logs for additional analysis.
        """
        def __load_rv_unit(file_diff : FileDiff):
            path = file_diff.file_path.replace('\\', '\\\\') # \\ 처리
            rv = file_diff.revision
            query = f"MATCH (unit:RvUnit) WHERE unit.revision = '{rv}' AND unit.file_path = '{path}' RETURN unit"
            result = self.neo4j.do_query(query)
            if not result:
                return None
                # # If no nodes found, create a new one
                # unit = CUnit.parse(file_path=file_diff.filepath)
                # unit = RvUnit(unit, rv)
                # to_save_datas.append(unit)
            elif len(result) == 1:
                node: Node = result[0]['unit']
                unit = dict2RvUnit(dict(node))
            else:
                raise Exception(f"Multiple nodes found for revision {rv} and file {path} {len(result)}")
            return unit

        #1. 파싱이 필요한 파일 특정 (일단 cpp, h만)
        print('1. check to parse files')
        to_parse_files = []
        for log, file_diffs in self.search_datas.values():
            for diff in file_diffs:
                file_path:str = diff.file_path
                if file_path.endswith('.cpp') or file_path.endswith('.h'):
                    to_parse_files.append(diff)
                    SVNManager.do_update(file_path, log.revision) #안전한 파싱을 위해 일단 업데이트는 수행

            #2. 파싱 및 db 로드
            print('2. parse/load files')
            to_save_datas = []
            to_add_relations = []
            rv_units = []
            for file_diff in to_parse_files:
                if __load_rv_unit(file_diff) is None:
                    # Parse the file and create a new unit
                    unit = CUnit.parse(file_path=file_diff.file_path)
                    unit = RvUnit(unit, file_diff.revision)
                    rv_units.append(unit)
                    to_save_datas.append(unit)
                else:
                    print('load_rv_unit ', file_diff.file_path)


            #2.1. 새로 파싱한 유닛의 경우 rvinfo 추가 생성
            print('2.1 parse rvinfo')
            for rvunit in rv_units:
                rv_infos = self.parse_for_rvinfo(rvunit.cunit, rvunit.revision)
                to_save_datas.extend(rv_infos)
                for rvinfo in rv_infos:
                    to_add_relations.append((rvunit, rvinfo, 'has'))


            #3. DB에 저장
            print('3. save db')
            print('before save_db ', len(to_save_datas), '/', len(to_add_relations))
            self.neo4j.print_info()
            self.neo4j.save_data(to_save_datas)
            self.neo4j.add_relationship(to_add_relations)
            print('after save_db ', len(to_save_datas), '/', len(to_add_relations))
            self.neo4j.print_info()





        # if not self.search_datas:
        #     raise Exception("No data to parse. Please search for logs first.")
        #
        # # Count file changes by extension
        # extensions = {}
        # for log, file_diffs in self.search_datas.values():
        #     for diff in file_diffs:
        #         ext = os.path.splitext(diff.filepath)[1]
        #         if ext:
        #             extensions[ext] = extensions.get(ext, 0) + 1
        #
        # print(f"File extensions found: {extensions}")
        # return {"parsed_data": extensions}

    def save_db_route(self):
        try:
            self.save_db()
            return {"message": "Database saved successfully"}
        except Exception as e:
            return {"message": f"Error saving database: {str(e)}"}, 500

    def parse_data_route(self):
        try:
            result = self.parse_data()
            return jsonify({"message": "Data parsed successfully", "data": result})
        except Exception as e:
            return jsonify({"message": f"Error parsing data: {str(e)}"}), 500

    def index(self):
        logs = None
        log_error = None
        search_params = None

        if request.method == 'POST':
            path = request.form.get('path')
            query_type = request.form.get('query_type', 'recent')

            # Prepare search parameters to display
            search_params = {
                'path': path,
                'query_type': query_type
            }

            # 1. 로그맵 구하기
            try:
                # 1.a 최근 로그
                if query_type == 'recent':
                    count = int(request.form.get('count', 50))
                    search_params['count'] = count
                    logs_map = SVNManager.get_recent_logs(path, count)
                else:  # 1.b. 범위 로그
                    start_revision = request.form.get('start_revision')
                    end_revision = request.form.get('end_revision')
                    search_params['start_revision'] = start_revision

                    if not end_revision:
                        # If end_revision is not provided, use the current revision
                        end_revision = SVNManager.get_current_revision(path)

                    search_params['end_revision'] = end_revision
                    logs_map = SVNManager.get_svn_range_log_dif(path, start_revision, end_revision)

                self.search_datas = logs_map
                search_params['revisions_found'] = len(logs_map)

                # 2. 로그맵을 시각화
                logs = []
                for revision, (log, file_diffs) in logs_map.items():
                    preview_msg, preview_path = self.get_preview_texts(log, file_diffs)

                    logs.append((revision, {
                        'log': log,
                        'file_diffs': file_diffs,
                        'preview_msg': preview_msg,
                        'preview_path': preview_path
                    }))

                # Sort logs by revision number (descending)
                logs.sort(key=lambda x: int(x[0]), reverse=True)

            except Exception as e:
                log_error = f"로그를 가져오는 중 오류 발생: {e}"

        return render_template_string(self.HTML_TEMPLATE, logs=logs, log_error=log_error, search_params=search_params)

    def run(self, debug=True):
        self.app.run(debug=debug)

    # HTML template as a class property
    HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
    <title>SVN Log Viewer</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1 { color: #333; }
        form { margin-bottom: 20px; padding: 15px; background-color: #f5f5f5; border-radius: 5px; }
        .form-row { margin-bottom: 10px; display: flex; align-items: center; }
        .form-row label { margin-right: 10px; min-width: 100px; }
        input[type="text"], input[type="number"] { padding: 8px; width: 200px; }
        button { padding: 8px 16px; background-color: #4CAF50; color: white; border: none; cursor: pointer; margin-right: 10px; }
        button:hover { background-color: #45a049; }
        .log-entry { margin-bottom: 20px; border: 1px solid #ddd; padding: 15px; border-radius: 5px; }
        .log-header { background-color: #f5f5f5; padding: 10px; margin-bottom: 10px; display: flex; justify-content: space-between; }
        .log-message { white-space: pre-wrap; background-color: #f9f9f9; padding: 10px; border-left: 3px solid #4CAF50; }
        .file-changes { margin-top: 10px; }
        .file-change { padding: 5px; margin: 5px 0; border-bottom: 1px solid #eee; }
        .file-change-modified { color: #ff9800; }
        .file-change-added { color: #4CAF50; }
        .file-change-deleted { color: #f44336; }
        .collapsible { cursor: pointer; padding: 8px; background-color: #f0f0f0; border-radius: 4px; margin: 5px 0; }
        .collapsible:hover { background-color: #e0e0e0; }
        .content { display: none; overflow: hidden; }
        .active { display: block; }
        .controls { margin-top: 10px; display: flex; }
        .radio-group { margin: 10px 0; }
        .radio-group label { margin-right: 15px; cursor: pointer; }
        .range-inputs { display: none; }
        .count-input { display: block; }
        .modal { display: none; position: fixed; z-index: 1; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.4); }
        .modal-content { background-color: #fefefe; margin: 15% auto; padding: 20px; border: 1px solid #888; width: 80%; border-radius: 5px; }
        .close { color: #aaa; float: right; font-size: 28px; font-weight: bold; cursor: pointer; }
        .close:hover { color: black; }
        #parse-results { margin-top: 15px; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
        .search-info { 
            position: fixed; 
            top: 80px; 
            right: 20px; 
            width: 250px; 
            background-color: #f8f8f8; 
            border: 1px solid #ddd; 
            border-radius: 5px; 
            padding: 15px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .search-info h3 { 
            margin-top: 0; 
            border-bottom: 1px solid #ddd; 
            padding-bottom: 8px; 
        }
        .search-info p { 
            margin: 5px 0; 
            font-size: 14px; 
        }
        .search-info-item { 
            display: flex; 
            justify-content: space-between; 
            margin-bottom: 5px;
        }
        .search-info-label { 
            font-weight: bold; 
            color: #555;
        }
        .main-content {
            margin-right: 280px;
        }
    </style>
    <script>
        function toggleContent(id) {
            const content = document.getElementById(id);
            content.classList.toggle("active");
        }

        function toggleQueryType() {
            const queryType = document.querySelector('input[name="query_type"]:checked').value;
            document.getElementById('range-inputs').style.display = queryType === 'range' ? 'block' : 'none';
            document.getElementById('count-input').style.display = queryType === 'recent' ? 'block' : 'none';
        }
    </script>
</head>
<body>
    <h1>SVN Log Viewer</h1>
    <form method="post">
        <div class="form-row">
            <label for="path">Repository Path:</label>
            <input type="text" name="path" id="path" placeholder="파일 또는 폴더 경로 입력" required>
        </div>

        <div class="radio-group">
            <label><input type="radio" name="query_type" value="recent" checked onclick="toggleQueryType()"> Recent logs</label>
            <label><input type="radio" name="query_type" value="range" onclick="toggleQueryType()"> Revision range</label>
        </div>

        <div id="count-input" class="form-row count-input">
            <label for="count">Number of logs:</label>
            <input type="number" name="count" id="count" value="50" min="1" max="1000">
        </div>

        <div id="range-inputs" class="form-row range-inputs">
            <label for="start_revision">Start Revision:</label>
            <input type="text" name="start_revision" id="start_revision" placeholder="Start (e.g., 1000)">
            <label for="end_revision" style="margin-left: 10px;">End Revision:</label>
            <input type="text" name="end_revision" id="end_revision" placeholder="End (e.g., 1050)">
        </div>

        <div class="controls">
            <button type="submit">로그 조회</button>
            <button type="button" onclick="saveDB()">Save DB</button>
            <button type="button" onclick="parseData()">Parsing</button>
        </div>
    </form>

    <div id="parseModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h2>Parsing Results</h2>
            <div id="parse-results"></div>
        </div>
    </div>

    {% if search_params %}
    <div class="search-info">
        <h3>Search Information</h3>
        <div class="search-info-item">
            <span class="search-info-label">Repository:</span>
            <span>{{ search_params.path }}</span>
        </div>
        <div class="search-info-item">
            <span class="search-info-label">Query Type:</span>
            <span>{{ search_params.query_type }}</span>
        </div>
        {% if search_params.query_type == 'recent' %}
        <div class="search-info-item">
            <span class="search-info-label">Count:</span>
            <span>{{ search_params.count }}</span>
        </div>
        {% else %}
        <div class="search-info-item">
            <span class="search-info-label">Start Revision:</span>
            <span>{{ search_params.start_revision }}</span>
        </div>
        <div class="search-info-item">
            <span class="search-info-label">End Revision:</span>
            <span>{{ search_params.end_revision }}</span>
        </div>
        {% endif %}
        <div class="search-info-item">
            <span class="search-info-label">Revisions Found:</span>
            <span>{{ search_params.revisions_found }}</span>
        </div>
    </div>
    {% endif %}

    <div class="main-content">
        {% if log_error %}
            <div class="error">{{ log_error }}</div>
        {% endif %}

        {% if logs %}
            <h2>로그 결과 ({{ logs|length }} entries)</h2>
            {% for revision, data in logs %}
            <div class="log-entry">
                <div class="log-header">
                    <div><strong>Revision:</strong> {{ data.log.revision }}</div>
                    <div><strong>Author:</strong> {{ data.log.author }}</div>
                    <div><strong>Date:</strong> {{ data.log.date.strftime('%Y-%m-%d %H:%M:%S') }}</div>
                </div>

                <div onclick="toggleContent('message-{{ data.log.revision }}')" class="collapsible">
                    <strong>Message:</strong> {{ data.preview_msg }}
                </div>
                <div id="message-{{ data.log.revision }}" class="content log-message">{{ data.log.msg }}
                </div>

                <div onclick="toggleContent('files-{{ data.log.revision }}')" class="collapsible">
                    <strong>Changed Files ({{ data.file_diffs|length }})</strong>: {{ data.preview_path }}
                </div>
                <div id="files-{{ data.log.revision }}" class="content file-changes">
                    {% for file_diff in data.file_diffs %}
                        <div class="file-change file-change-{{ file_diff.action.name|lower }}">
                            <strong>{{ file_diff.action.value }}:</strong> {{ file_diff.filepath }}
                        </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        {% endif %}
    </div>

    <script>
        function saveDB() {
            fetch('/save_db', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error saving to database');
            });
        }

        function parseData() {
            fetch('/parse_data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                displayParseResults(data);
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error parsing data');
            });
        }

        function displayParseResults(data) {
            const resultsDiv = document.getElementById('parse-results');
            let html = '';

            if (data.message) {
                html += `<p>${data.message}</p>`;
            }

            if (data.data && data.data.parsed_data) {
                html += '<h3>File Extensions</h3>';
                html += '<table style="width:100%; border-collapse: collapse;">';
                html += '<tr><th style="text-align:left; padding:8px; border-bottom:1px solid #ddd;">Extension</th>';
                html += '<th style="text-align:left; padding:8px; border-bottom:1px solid #ddd;">Count</th></tr>';

                for (const [ext, count] of Object.entries(data.data.parsed_data)) {
                    html += `<tr><td style="padding:8px; border-bottom:1px solid #ddd;">${ext || '(no extension)'}</td>`;
                    html += `<td style="padding:8px; border-bottom:1px solid #ddd;">${count}</td></tr>`;
                }

                html += '</table>';
            }

            resultsDiv.innerHTML = html;
            document.getElementById('parseModal').style.display = 'block';
        }

        function closeModal() {
            document.getElementById('parseModal').style.display = 'none';
        }

        // Close modal when clicking outside of it
        window.onclick = function(event) {
            const modal = document.getElementById('parseModal');
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        }

        // Initialize form display
        toggleQueryType();
    </script>
</body>
</html>
"""


# Main application entry point
if __name__ == '__main__':
    viewer = SVNLogViewer()
    viewer.run(debug=True)