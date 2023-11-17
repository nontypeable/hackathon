import socket

class Config():
    cameras = {
        "hash": {
            "path": "your-path",
            "url": "your-url"
        },
    }
    rtsp_port = 4554
    start_udp_port = 5550
    local_ip = socket.gethostbyname(socket.gethostname())
    web_limit = 2
    log_file = ""