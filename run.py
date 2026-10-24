"""Ponto de entrada: python run.py  -> abre http://127.0.0.1:8000"""
import threading, webbrowser, uvicorn

HOST, PORT = "127.0.0.1", 8000

if __name__ == "__main__":
    threading.Timer(1.5, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    uvicorn.run("app.server:app", host=HOST, port=PORT)
