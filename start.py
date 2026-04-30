import threading
from bot import run_bot
from web import run_web

def start_web():
    run_web()

threading.Thread(target=start_web).start()

run_bot()