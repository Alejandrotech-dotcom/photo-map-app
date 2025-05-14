# run_app.py
from app import app
import webbrowser
import threading

if __name__ == '__main__':
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=False)
