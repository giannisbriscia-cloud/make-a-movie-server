from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import subprocess, tempfile, os, uuid, json

app = Flask(__name__)
CORS(app)

sessions = {}

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/session", methods=["POST"])
def create_session():
    sid = uuid.uuid4().hex[:12]
    d = tempfile.mkdtemp()
    sessions[sid] = {"dir": d, "clips": {}, "soundtrack": None}
    return jsonify({"session_id": sid})

@app.route("/upload_clip", methods=["POST"])
def upload_clip():
    sid = request.form.get("session_id")
    idx = int(request.form.get("index", 0))
    f = request.files.get("clip")
    if not sid or sid not in sessions or not f:
        return jsonify({"error": "invalid"}), 400
    d = sessions[sid]["dir"]
    p = os.path.join(d, "clip_" + str(idx) + ".webm")
    f.save(p)
    sessions[sid]["clips"][idx] = p
    return jsonify({"ok": True})

@app.route("/upload_soundtrack", methods=["POST"])
def upload_soundtrack():
    sid = request.form.get("session_id")
    f = request.files.get("soundtrack")
    if not sid or sid not in sessions or not f:
        return jsonify({"error": "invalid"}), 400
    d = sessions[sid]["dir"]
    p = os.path.join(d, "soundtrack.mp3")
    f.save(p)
    sessions[sid]["soundtrack"] = p
    return jsonify({"ok": True})

@app.route("/merge_session", methods=["POST"])
def merge_session():
    try:
        data = request.get_json()
        sid = data.get("session_id")
        order = data.get("order", [])
        ss = float(data.get("soundtrack_start", 0))
        fo = float(data.get("fade_out", 4))
        if not sid or sid not in sessions:
            return jsonify({"error": "session not found"}), 400
        s = sessions[sid]
        d = s["dir"]
        clips = s["clips"]
        cp = [clips[i] for i in order if i in clips]
        if not cp:
            return jsonify({"error": "no clips"}), 400
        lp = os.path.join(d, "list.txt")
        with open(lp, "w") as lf:
            for p in cp:
                lf.write("file '" + p + "'" + chr(10))
        mp = os.path.join(d, "merged.mp4")
        subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",lp,"-c","copy",mp], check=True, capture_output=True)
        op = os.path.join(d, "out_" + uuid.uuid4().hex[:8] + ".mp4")
        st = s.get("soundtrack")
        if st and os.path.exists(st):
            dur = float(json.loads(subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format",mp], capture_output=True, text=True).stdout)["format"]["duration"])
            fs = max(0, dur - fo)
            subprocess.run(["ffmpeg","-y","-i",mp,"-ss",str(ss),"-i",st,"-filter_complex","[1:a]atrim=start="+str(ss)+",asetpts=PTS-STARTPTS,afade=t=out:st="+str(fs)+":d="+str(fo)+"[sa];[0:a][sa]amix=inputs=2:duration=first[aout]","-map","0:v","-map","[aout]","-c:v","copy","-c:a","aac","-shortest",op], check=True, capture_output=True)
        else:
            op = mp
        del sessions[sid]
        return send_file(op, mimetype="video/mp4", as_attachment=True, download_name="make-a-movie.mp4")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
