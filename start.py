"""
Start de Instagram-generator (werkt op Windows, Mac en Linux).
    python start.py
Daarna openen in de browser: http://localhost:8080
"""
import os
import socket

from app import app

PORT = int(os.environ.get("PORT", "8080"))


def eigen_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "localhost"


if __name__ == "__main__":
    print()
    print("  Gemeentebelangen Instagram-generator draait.")
    print(f"  Op deze computer:          http://localhost:{PORT}")
    print(f"  Vanaf andere apparaten:    http://{eigen_ip()}:{PORT}")
    print("  Stoppen: sluit dit venster (of Ctrl+C).")
    print()
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=PORT, threads=4)
    except ImportError:
        app.run(host="0.0.0.0", port=PORT)
