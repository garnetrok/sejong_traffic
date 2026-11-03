import os
from pathlib import Path

from flask import Flask, Response, jsonify, request

from dashboard_api import API_FUNCTIONS
from save_predictions import run_and_save

app = Flask(__name__)
WEB_DIR = Path(__file__).parent / "web"


@app.before_request
def require_password():
    """DASHBOARD_PASSWORD 환경 변수를 설정하면 접속 시 비밀번호를 물어봄 (아이디는 아무거나)."""
    password = os.environ.get("DASHBOARD_PASSWORD")
    if not password or request.path == "/health":
        return None
    auth = request.authorization
    if auth and auth.password == password:
        return None
    return Response("비밀번호가 필요합니다.", 401, {"WWW-Authenticate": 'Basic realm="SafeRoad AI"'})


def _read(name: str) -> str:
    return (WEB_DIR / name).read_text(encoding="utf-8")


@app.route("/")
def dashboard():
    html = _read("index.html")
    html = html.replace("<?!= include('style'); ?>", _read("style.html"))
    html = html.replace(
        "<?!= include('script'); ?>",
        "<script>\n" + _read("server-bridge.js") + "\n</script>\n" + _read("script.html"),
    )
    return Response(html, mimetype="text/html")


@app.route("/api/<name>", methods=["POST"])
def call_api(name):
    func = API_FUNCTIONS.get(name)
    if func is None:
        return jsonify({"error": f"알 수 없는 함수: {name}"}), 404
    args = (request.get_json(silent=True) or {}).get("args", [])
    try:
        return jsonify({"result": func(*args)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/recompute", methods=["POST"])
def recompute():
    try:
        run_and_save()
        return jsonify({"status": "success", "message": "예측 및 저장 완료"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
