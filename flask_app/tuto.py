from flask import Flask, request, render_template_string
import svn_manager.svn_manager as SVNManager

app = Flask(__name__)

# Improved HTML template with better structure and styling
HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
    <title>SVN Log Viewer</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1 { color: #333; }
        form { margin-bottom: 20px; }
        input[type="text"] { padding: 8px; width: 400px; }
        button { padding: 8px 16px; background-color: #4CAF50; color: white; border: none; cursor: pointer; }
        button:hover { background-color: #45a049; }
        .log-entry { margin-bottom: 20px; border: 1px solid #ddd; padding: 15px; border-radius: 5px; }
        .log-header { background-color: #f5f5f5; padding: 10px; margin-bottom: 10px; display: flex; justify-content: space-between; }
        .log-message { white-space: pre-wrap; background-color: #f9f9f9; padding: 10px; border-left: 3px solid #4CAF50; }
        .file-changes { margin-top: 10px; }
        .file-change { padding: 5px; margin: 5px 0; border-bottom: 1px solid #eee; }
        .file-change-modified { color: #ff9800; }
        .file-change-added { color: #4CAF50; }
        .file-change-deleted { color: #f44336; }
        .collapsible { cursor: pointer; }
        .content { display: none; overflow: hidden; }
        .active { display: block; }
    </style>
    <script>
        function toggleContent(id) {
            const content = document.getElementById(id);
            content.classList.toggle("active");
        }
    </script>
</head>
<body>
    <h1>SVN Log Viewer</h1>
    <form method="post">
        <input type="text" name="path" placeholder="파일 또는 폴더 경로 입력" required>
        <button type="submit">로그 조회</button>
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
                    <strong>Message</strong> (click to expand/collapse)
                </div>
                <div id="message-{{ data.log.revision }}" class="content log-message">
                    {{ data.log.msg }}
                </div>

                <div onclick="toggleContent('files-{{ data.log.revision }}')" class="collapsible">
                    <strong>Changed Files</strong> ({{ data.file_diffs|length }}) (click to expand/collapse)
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
</body>
</html>
"""


@app.route('/', methods=['GET', 'POST'])
def index():
    logs = None
    log_error = None

    if request.method == 'POST':
        path = request.form.get('path')
        try:
            # Get the SVN logs
            logs_map = SVNManager.get_recent_logs(path)

            # Transform the data for template rendering
            logs = []
            for revision, (log, file_diffs) in logs_map.items():
                logs.append((revision, {
                    'log': log,
                    'file_diffs': file_diffs
                }))

            # Sort logs by revision number (descending)
            logs.sort(key=lambda x: int(x[0]), reverse=True)

        except Exception as e:
            log_error = f"로그를 가져오는 중 오류 발생: {e}"

    return render_template_string(HTML_TEMPLATE, logs=logs, log_error=log_error)


if __name__ == '__main__':
    app.run(debug=True)