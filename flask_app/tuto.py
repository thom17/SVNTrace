from flask import Flask, request, render_template_string
import svn_manager.svn_manager as SVNManager
from svn_manager.svn_data import Log, FileDiff
import os

app = Flask(__name__)

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
        </div>
    </form>

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
                    <strong> {{data.preview_msg}} </strong>
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
    {% elif log_error %}
        <div class="error">{{ log_error }}</div>
    {% endif %}

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

        // Initialize form display
        toggleQueryType();
    </script>
</body>
</html>
"""


def get_preview_texts(log: Log, file_diffs: list[FileDiff]) -> tuple[str, str]:
    # Get first line of commit message
    msg = ""
    if log.msg and '\n' in log.msg:
        msg = log.msg.split('\n')[0]
    else:
        msg = log.msg or ""

    # Get filenames without paths
    filenames = [os.path.basename(diff.filepath) for diff in file_diffs]
    return msg, ", ".join(filenames)


@app.route('/save_db', methods=['POST'])
def save_db_route():
    try:
        save_db()
        return {"message": "Database saved successfully"}
    except Exception as e:
        return {"message": f"Error saving database: {str(e)}"}, 500


def save_db():
    """
    Save the SVN logs to a database.
    """
    # Placeholder for database save logic
    print('clicked save_db')
    pass


@app.route('/', methods=['GET', 'POST'])
def index():
    logs = None
    log_error = None

    if request.method == 'POST':
        path = request.form.get('path')
        query_type = request.form.get('query_type', 'recent')

        try:
            if query_type == 'recent':
                count = int(request.form.get('count', 50))
                logs_map = SVNManager.get_recent_logs(path, count)
            else:  # range
                start_revision = request.form.get('start_revision')
                end_revision = request.form.get('end_revision')

                if not end_revision:
                    # If end_revision is not provided, use the current revision
                    end_revision = SVNManager.get_current_revision(path)

                logs_map = SVNManager.get_svn_range_log_dif(path, start_revision, end_revision)

            # Transform the data for template rendering
            logs = []
            for revision, (log, file_diffs) in logs_map.items():
                preview_msg, preview_path = get_preview_texts(log, file_diffs)

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

    return render_template_string(HTML_TEMPLATE, logs=logs, log_error=log_error)


if __name__ == '__main__':
    app.run(debug=True)