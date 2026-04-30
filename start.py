import threading
from bot import run_bot
from web import app

def run_web():
    app.run(host="0.0.0.0", port=8000, debug=False)

threading.Thread(target=run_web, daemon=True).start()

run_bot()