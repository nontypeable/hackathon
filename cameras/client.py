import asyncio
import re
import string
import time
from random import choices, randrange
from config import Config
from shared import Shared
from log import Log

class Client():
    def __init__(self):
        self.camera_hash = None
        self.udp_ports = {}

    @staticmethod
    async def listen():
        """
        Здесь мы слушаем подключения клиентов
        """

        host = "0.0.0.0"
        print(f'*** Start listening {host}:{Config.rtsp_port} ***\n')

        loop = asyncio.get_running_loop()
        server = await loop.create_server(
            lambda: Client(), host, Config.rtsp_port
        )
        
        async with server:
            await server.serve_forever()

    def handle_request(self, transport, host, data):
        ask, option = self._request(data)
        session_id = self._get_session_id(ask)

        if option == 'OPTIONS':
            self._response(
                transport,
                'Public: OPTIONS, DESCRIBE, SETUP, TEARDOWN, PLAY')

        if option == 'DESCRIBE':
            sdp = self._get_description()
            self._response(
                transport,
                'Content-Type: application/sdp',
                f'Content-Length: {len(sdp) + 2}',
                '',
                sdp)

        elif option == 'SETUP':
            udp_ports = self._get_ports(ask)
            track_id = 'track1' if not self.udp_ports else 'track2'
            self.udp_ports[track_id] = udp_ports
            self._response(
                transport,
                f'Transport: RTP/AVP;unicast;client_port={udp_ports[0]}-{udp_ports[1]};server_port=5998-5999',
                f'Session: {session_id};timeout=60')

        elif option == 'PLAY':
            self._response(
                transport,
                f'Session: {session_id}',
                self._get_rtp_info())

            # if session_id not in Shared.data[self.camera_hash]['clients']:
            Shared.data[self.camera_hash]['clients'][session_id] = {
                'host': host, 'ports': self.udp_ports, 'transport': transport}

            self._check_web_limit(host)

            Log.add(f'Play [{self.camera_hash}] [{session_id}] [{host}]')

        elif option == 'TEARDOWN':
            self._response(transport, f'Session: {session_id}')

        return self.camera_hash, session_id

    def _get_rtp_info(self):
        rtp_info = Shared.data[self.camera_hash]['rtp_info']

        print(rtp_info)

        delta = time.time() - rtp_info['starttime']
        rtptime = int(rtp_info["rtptime"][0]) + int(delta * 90000)
        # 90000 is clock frequency in SDP a=rtpmap:96 H26*/90000

        res = f'RTP-Info: url=rtsp://{Config.local_ip}:{Config.rtsp_port}/track1;' \
            f'seq={rtp_info["seq"][0]};rtptime={rtptime}'

        if len(rtp_info['seq']) < 2:
            return res

        rtptime = int(rtp_info["rtptime"][1]) + int(delta * 8000)
        # 90000 is clock frequency in SDP a=rtpmap:8 PCMA/8000

        res += f',url=rtsp://{Config.local_ip}:{Config.rtsp_port}/track2;' \
            f'seq={rtp_info["seq"][1]};rtptime={rtptime}'

        return res

    def _request(self, data):
        try:
            ask = data.decode()
        except Exception:
            raise RuntimeError(f"can't decode this ask:\n{data}")

        print(f'*** Ask:\n{ask}')
        # res = re.match(r'(.+?) rtsps?://.+?:\d+/(.+?)(/track.*?)? .+?\r\n', ask)
        res = re.match(r'(.+?) rtsps?://.+?:\d+/?(.*?) .+?\r\n', ask)
        if not res:
            raise RuntimeError('invalid ask')

        self.cseq = self._get_cseq(ask)

        if not self.camera_hash:
            hash = res.group(2)
            if hash not in Config.cameras:
                raise RuntimeError('invalid camera hash')
            if hash not in Shared.data:
                raise RuntimeError('camera is offline')
            self.camera_hash = hash

        return ask, res.group(1)

    def _response(self, transport, *lines):
        reply = 'RTSP/1.0 200 OK\r\n' \
            f'CSeq: {self.cseq}\r\n'

        for row in lines:
            reply += f'{row}\r\n'
        reply += '\r\n'

        transport.write(reply.encode())

        print(f'*** Reply:\n{reply}')

    def _get_cseq(self, ask):
        res = re.match(r'.+?\r\nCSeq: (\d+)', ask, re.DOTALL)
        if not res:
            raise RuntimeError('invalid incoming CSeq')
        return int(res.group(1))

    def _get_session_id(self, ask):
        res = re.match(r'.+?\nSession: *([^;\r\n]+)', ask, re.DOTALL)
        if res:
            return res.group(1).strip()

        return ''.join(choices(string.ascii_lowercase + string.digits, k=9))

    def _get_ports(self, ask):
        res = re.match(r'.+?\nTransport:[^\n]+client_port=(\d+)-(\d+)', ask, re.DOTALL)
        if not res:
            raise RuntimeError('invalid transport ports')
        return [int(res.group(1)), int(res.group(2))]

    def _get_description(self):
        sdp = Shared.data[self.camera_hash]['description']
        res = 'v=0\r\n' \
            f'o=- {randrange(100000, 999999)} {randrange(1, 10)} IN IP4 {Config.local_ip}\r\n' \
            's=python-rtsp-server\r\n' \
            't=0 0'

        if not sdp['video']:
            return res
        res += f'\r\nm=video {sdp["video"]["media"]}\r\n' \
            'c=IN IP4 0.0.0.0\r\n' \
            f'b={sdp["video"]["bandwidth"]}\r\n' \
            f'a=rtpmap:{sdp["video"]["rtpmap"]}\r\n' \
            f'a=fmtp:{sdp["video"]["format"]}\r\n' \
            'a=control:track1'

        if not sdp['audio']:
            return res
        res += f'\r\nm=audio {sdp["audio"]["media"]}\r\n' \
            f'a=rtpmap:{sdp["audio"]["rtpmap"]}\r\n' \
            'a=control:track2'
        return res

    def _check_web_limit(self, host):
        if not Config.web_limit or self._get_client_type(host) == 'local':
            return
        web_sessions = []
        for session_id, data in Shared.data[self.camera_hash]['clients'].items():
            if self._get_client_type(data['host']) == 'web':
                web_sessions.append(session_id)
        if len(web_sessions) > Config.web_limit:
            ws = web_sessions[:-Config.web_limit]
            for session_id in ws:
                print('Web limit exceeded, cloce old connection\n')
                Shared.data[self.camera_hash]['clients'][session_id]['transport'].close()
                # Shared.data item will be deleted by ClientTcpProtocol.connection_lost callback

    def _get_client_type(self, host):
        if host == '127.0.0.1' \
            or host == 'localhost' \
                or (host.startswith('192.168.') and host != Config.local_ip):
            return 'local'
        return 'web'


class ClientTcpProtocol(asyncio.Protocol):
    def __init__(self):
        self.client = Client()
        self.camera_hash, self.session_id = None, None
        # self.event = event

    def connection_made(self, transport):
        peername = transport.get_extra_info('peername')
        self.transport = transport
        self.host = peername[0]
        print(f'*** New connection from {peername[0]}:{peername[1]} ***\n\n')

    def data_received(self, data):
        try:
            self.camera_hash, self.session_id = self.client.handle_request(self.transport, self.host, data)
        except Exception as e:
            print(f'Error in clent request handler: {e}\n\n')
            self.transport.close()

    def connection_lost(self, exc):
        if not self.session_id or self.session_id not in Shared.data[self.camera_hash]['clients']:
            return
        del(Shared.data[self.camera_hash]['clients'][self.session_id])
        Log.add(f'Close [{self.camera_hash}] [{self.session_id}] [{self.host}]')
