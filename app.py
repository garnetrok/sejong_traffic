from flask import Flask, jsonify
from save_predictions import run_and_save

app = Flask(__name__)


@app.route("/")
def home():
    return "Flask 서버 작동중!"


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
    app.run(debug=True, port=5000)
