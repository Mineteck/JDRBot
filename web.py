from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import shared

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# 🌐 PAGE WEB
@app.route("/")
def home():
    return render_template("index.html")


# 🔥 API STATE (fallback)
@app.route("/state")
def state():
    return {
        "current": shared.current,
        "queue": shared.queues,
        "loop": shared.loop
    }


# 🔁 CONTROLS
@app.route("/pause", methods=["POST"])
def pause():
    for vc in shared.bot.voice_clients:
        vc.pause()
    return {"ok": True}


@app.route("/resume", methods=["POST"])
def resume():
    for vc in shared.bot.voice_clients:
        vc.resume()
    return {"ok": True}


@app.route("/skip", methods=["POST"])
def skip():
    for vc in shared.bot.voice_clients:
        vc.stop()
    return {"ok": True}


@app.route("/loop/<mode>", methods=["POST"])
def loop(mode):
    if mode == "song":
        shared.loop["song"] = not shared.loop["song"]
    elif mode == "queue":
        shared.loop["queue"] = not shared.loop["queue"]

    return {"ok": True}


# 🔥 PUSH LIVE DATA
def emit_update():
    socketio.emit("update", {
        "current": shared.current,
        "queue": shared.queues,
        "loop": shared.loop
    })


# boucle broadcast (live dashboard)
def background_updater():
    import time
    while True:
        socketio.sleep(1)
        emit_update()


socketio.start_background_task(background_updater)


def run_web():
    socketio.run(app, host="0.0.0.0", port=8000)