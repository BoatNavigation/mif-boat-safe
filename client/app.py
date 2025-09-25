from flask import Flask, request, render_template_string
import socket, ssl, json

app = Flask(__name__)

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8443
CA_FILE = "server.crt"

HTML = """
<form method="post">
    <select name="direction">
        <option value="forward">Forward</option>
        <option value="backward">Backward</option>
        <option value="left">Left</option>
        <option value="right">Right</option>
        <option value="stop">Stop</option>
    </select>
    Duty: <input name="duty" type="number" value="20">
    Duration: <input name="duration" type="number" value="0" step="0.1">
    <input type="submit" value="Send">
</form>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        cmd = {
            "direction": request.form["direction"],
            "duty": int(request.form.get("duty", 20)),
            "duration": float(request.form.get("duration", 0))
        }
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=CA_FILE)
        with socket.create_connection((SERVER_HOST, SERVER_PORT)) as sock:
            with context.wrap_socket(sock, server_hostname="raspberrypi") as ssock:
                ssock.sendall((json.dumps(cmd)+"\n").encode())
                resp = ssock.recv(4096)
        return f"Sent: {cmd}, Response: {resp.decode()}<br><a href='/'>Back</a>"
    return HTML

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
