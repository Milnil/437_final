from http.server import HTTPServer, SimpleHTTPRequestHandler
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class CORSHTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

def run_frontend_server(host="localhost", port=8000):
    server_address = (host, port)
    httpd = HTTPServer(server_address, CORSHTTPRequestHandler)
    logging.info(f"Frontend server started at http://{host}:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run_frontend_server() 