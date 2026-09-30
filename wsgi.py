"""
WSGI entry point for production servers.

Windows  → Waitress:
    python wsgi.py
    waitress-serve --threads=4 --port=5000 wsgi:app

Linux/Mac → Gunicorn:
    gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
"""
import os
import time

print("Starting FarmIt...")

t0 = time.time()
from app import create_app
app = create_app(os.environ.get('FLASK_CONFIG', 'development'))
print(f"App created in {time.time() - t0:.2f}s")

if __name__ == '__main__':
    from waitress import serve

    threads = int(os.environ.get('WAITRESS_THREADS', 4))
    port    = int(os.environ.get('PORT', 5000))
    host    = os.environ.get('HOST', '0.0.0.0')

    print(f"Serving on http://{host}:{port} with {threads} threads")
    serve(app, host=host, port=port, threads=threads)
