from flask import Flask, render_template, jsonify
import shared

app = Flask(__name__)


# 🌐 PAGE WEB
@app.route("/")
def home():
    return render_template("index.html")


# 🎶 musique actuelle
@app.route("/now")
def now():
    return jsonify(shared.current)


# 📜 queue
@app.route("/queue")
def queue():
    return jsonify(shared.queues)


# ⏯ pause
@app.route("/pause", methods=["POST"])
def pause():
    if shared.bot:
        for vc in shared.bot.voice_clients:
            vc.pause()
    return {"ok": True}


# ▶ resume
@app.route("/resume", methods=["POST"])
def resume():
    if shared.bot:
        for vc in shared.bot.voice_clients:
            vc.resume()
    return {"ok": True}

@app.route("/loop/<mode>", methods=["POST"])
def loop(mode):
    if mode == "song":
        shared.loop["song"] = not shared.loop["song"]

    if mode == "queue":
        shared.loop["queue"] = not shared.loop["queue"]

    return {"ok": True, "loop": shared.loop}

# ⏭ skip
@app.route("/skip", methods=["POST"])
def skip():
    if shared.bot:
        for vc in shared.bot.voice_clients:
            vc.stop()
    return {"ok": True}