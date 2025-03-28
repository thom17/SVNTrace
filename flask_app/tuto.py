from flask import Flask, request, render_template_string
import svn_manager.svn_manager as SVNManager  # SVN Util 프로젝트에서 제공하는 모듈이라고 가정

app = Flask(__name__)

# 간단한 HTML 템플릿 (실제 프로젝트에서는 별도의 템플릿 파일로 분리 가능)
HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
    <title>SVN Log Viewer</title>
</head>
<body>
    <h1>SVN Log Viewer</h1>
    <form method="post">
        <input type="text" name="path" placeholder="파일 또는 폴더 경로 입력" required>
        <button type="submit">로그 조회</button>
    </form>
    {% if log_data %}
        <h2>로그 결과:</h2>
        <pre>{{ log_data }}</pre>
    {% endif %}
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    log_data = None
    if request.method == 'POST':
        path = request.form.get('path')
        try:
            # SVN Util 프로젝트의 get_log 기능을 활용하여 해당 경로의 로그를 가져옴
            log_data = SVNManager.get_svn_logs(path)
        except Exception as e:
            log_data = f"로그를 가져오는 중 오류 발생: {e}"
    return render_template_string(HTML_TEMPLATE, log_data=log_data)



if __name__ == '__main__':
    app.run(debug=True)
