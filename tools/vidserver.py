# -*- coding: utf-8 -*-
"""本地接收视频的小服务器：POST /save?name=xxx 存文件并落 .done 标记。"""
import http.server
import os
import socketserver
import sys
import urllib.parse

OUT = sys.argv[1] if len(sys.argv) > 1 else 'out'
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
os.makedirs(OUT, exist_ok=True)


class H(http.server.BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == '/save':
            name = urllib.parse.parse_qs(u.query).get('name', ['video.webm'])[0]
            name = os.path.basename(name)
            n = int(self.headers.get('Content-Length', 0))
            data = self.rfile.read(n)
            with open(os.path.join(OUT, name), 'wb') as f:
                f.write(data)
            with open(os.path.join(OUT, name + '.done'), 'w') as f:
                f.write('ok')
            self.send_response(200)
            self._cors()
            self.end_headers()
            self.wfile.write(b'ok')
            print('saved', name, len(data), flush=True)
        elif u.path == '/done':
            self.send_response(200)
            self._cors()
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    do_GET = do_POST

    def log_message(self, *a):
        pass


socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(('127.0.0.1', PORT), H) as httpd:
    print('serving out=%s port=%d' % (OUT, PORT), flush=True)
    httpd.serve_forever()
