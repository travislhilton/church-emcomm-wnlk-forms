"""Stand-in for the Winlink Express form server: logs every multipart POST field to a file."""
import sys, json, io, pathlib, email
from email import policy
from http.server import BaseHTTPRequestHandler, HTTPServer

LOG = pathlib.Path(sys.argv[1])

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(n)
        ctype = self.headers.get('Content-Type', '')
        msg = email.message_from_bytes(b'Content-Type: ' + ctype.encode() + b'\r\nMIME-Version: 1.0\r\n\r\n' + raw, policy=policy.default)
        fields = {}
        files = []
        for part in msg.iter_parts():
            name = part.get_param('name', header='content-disposition')
            fname = part.get_filename()
            val = part.get_payload(decode=True).decode('utf-8', 'replace')
            if fname is not None:
                files.append((name, fname, len(val)))
            else:
                fields[name] = val
        rec = {'bytes': n, 'ctype': ctype, 'fields': fields, 'file_parts': files}
        with LOG.open('a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        body = b'<html><body><h3>POST received (test server)</h3><p>%d fields, %d file parts</p></body></html>' % (len(fields), len(files))
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a):
        pass

HTTPServer(('0.0.0.0', int(sys.argv[2])), H).serve_forever()
