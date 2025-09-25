#!/usr/bin/env python3
import socket
import ssl
import threading
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

clients = []

def handle_client(conn, addr):
    logging.info("Client connected: %s", addr)
    try:
        buf = b""
        while True:
            data = conn.recv(4096)
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line:
                    continue
                try:
                    cmd = json.loads(line.decode())
                except:
                    conn.sendall(b'{"status":"error","reason":"bad_json"}\n')
                    continue

                logging.info("Command received: %s", cmd)
                # пересылаем команду всем подключенным Pi
                for c in clients:
                    try:
                        c.sendall((json.dumps(cmd)+"\n").encode())
                    except:
                        pass

                conn.sendall(b'{"status":"ok"}\n')
    finally:
        conn.close()
        clients.remove(conn)
        logging.info("Client disconnected: %s", addr)

def main():
    HOST, PORT = "0.0.0.0", 8443
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile="server.crt", keyfile="server.key")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOST, PORT))
    sock.listen(5)
    logging.info("TLS server listening on %s:%d", HOST, PORT)

    try:
        while True:
            client_sock, addr = sock.accept()
            try:
                tls_conn = context.wrap_socket(client_sock, server_side=True)
            except ssl.SSLError as e:
                logging.warning("TLS handshake failed: %s", e)
                client_sock.close()
                continue
            clients.append(tls_conn)
            threading.Thread(target=handle_client, args=(tls_conn, addr), daemon=True).start()
    finally:
        sock.close()

if __name__ == "__main__":
    main()
