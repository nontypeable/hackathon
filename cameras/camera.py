import asyncio
import re
import time
from hashlib import md5
from shared import Shared
from config import Config
from log import Log

class Camera:
    def __init__(self, hash):
        self.hash = hash
        self.url = self._parse_url(Config.cameras[hash]['url'])

    async def connect(self):
        self.udp_ports = self._get_self_udp_ports()
        self.cseq = 1
        self.realm, self.nonce = None, None

        try:
            self.reader, self.writer = await asyncio.open_connection(self.url['host'], self.url['tcp_port'])
        except Exception as e:
            print(f"Can't connect to camera [{self.hash}]: {e}")
            return

        await self._request('OPTIONS', self.url['url'])

        reply, code = await self._request(
            'DESCRIBE',
            self.url['url'],
            'User-Agent: python-rtsp-server',
            'Accept: application/sdp')

        if code == 401:
            self.realm, self.nonce = self._get_auth_params(reply)

            reply, code = await self._request(
                'DESCRIBE',
                self.url['url'],
                'Accept: application/sdp')

        self.description = self._get_description(reply)

        track_ids = self._get_track_ids(reply)

        reply, code = await self._request(
            'SETUP',
            f'{self.url["url"]}/{track_ids[0]}',
            ('Transport: RTP/AVP;unicast;'
                f'client_port={self.udp_ports["track1"][0]}-{self.udp_ports["track1"][1]}'))

        self.session_id = self._get_session_id(reply)

        if len(track_ids) > 1:
            reply, code = await self._request(
                'SETUP',
                f'{self.url["url"]}/{track_ids[1]}',
                ('Transport: RTP/AVP;unicast;'
                    f'client_port={self.udp_ports["track2"][0]}-{self.udp_ports["track2"][1]}'),
                f'Session: {self.session_id}')

        reply, code = await self._request(
            'PLAY',
            self.url['url'],
            f'Session: {self.session_id}',
            'Range: npt=0.000-')

        Shared.data[self.hash] = {
            'description': self.description,
            'rtp_info': self._get_rtp_info(reply),
            # 'transports': {},
            'clients': {}}

        Log.add(f'Camera [{self.hash}] connected')

        await self._listen()

    async def _listen(self):
        await self._start_server('track1')

        if self.description['audio']:
            await self._start_server('track2')

    async def _request(self, option, url, *lines):
        command = f'{option} {url} RTSP/1.0\r\n' \
            f'CSeq: {self.cseq}\r\n'

        auth_line = self._get_auth_line(option)
        if auth_line:
            command += f'{auth_line}\r\n'

        for row in lines:
            if row:
                command += f'{row}\r\n'
        command += '\r\n'

        print(f'*** Ask:\n{command}')
        self.writer.write(command.encode())
        reply = (await self.reader.read(4096)).decode()
        print(f"*** Reply:\n{reply}")
        self.cseq += 1

        res = re.match(r'RTSP/1.0 (\d{3}) ([^\r\n]+)', reply)
        if not res:
            print('Error: invalid reply\n')
            return reply, 0
        return reply, int(res.group(1))

    def _get_auth_params(self, reply):
        realm_nonce = re.match(r'.+?\nWWW-Authenticate:.+?realm="(.+?)", ?nonce="(.+?)"', reply, re.DOTALL)
        if not realm_nonce:
            raise RuntimeError('Invalid digest auth reply')

        return realm_nonce.group(1), realm_nonce.group(2)

    def _get_auth_line(self, option):
        if not self.realm or not self.nonce:
            return
        ha1 = md5(f'{self.url["login"]}:{self.realm}:{self.url["password"]}'.encode('utf-8')).hexdigest()
        ha2 = md5(f'{option}:{self.url["url"]}'.encode('utf-8')).hexdigest()
        response = md5(f'{ha1}:{self.nonce}:{ha2}'.encode('utf-8')).hexdigest()
        line = f'Authorization: Digest username="{self.url["login"]}", ' \
            f'realm="{self.realm}" nonce="{self.nonce}", uri="{self.url["url"]}", response="{response}"'
        return line

    def _get_description(self, reply):
        blocks = reply.split('\r\n\r\n', 2)
        if len(blocks) < 2:
            raise RuntimeError('Invalid DESCRIBE reply')

        sdp = blocks[1].strip()

        details = {'video': {}, 'audio': {}}

        res = re.match(r'.+?\nm=video (.+?)\r\n', sdp, re.DOTALL)
        if res:
            details['video'] = {'media': res.group(1), 'bandwidth': '', 'rtpmap': '', 'format': ''}

            res = re.match(r'.+?\nm=video .+?\nb=([^\r\n]+)', sdp, re.DOTALL)
            if res:
                details['video']['bandwidth'] = res.group(1)

            res = re.match(r'.+?\nm=video .+?\na=rtpmap:([^\r\n]+)', sdp, re.DOTALL)
            if res:
                details['video']['rtpmap'] = res.group(1)

            res = re.match(r'.+?\nm=video .+?\na=fmtp:([^\r\n]+)', sdp, re.DOTALL)
            if res:
                details['video']['format'] = res.group(1)

        res = re.match(r'.+?\nm=audio (.+?)\r\n', sdp, re.DOTALL)
        if res:
            details['audio'] = {'media': res.group(1), 'rtpmap': ''}

            res = re.match(r'.+?\nm=audio .+?\na=rtpmap:([^\r\n]+)', sdp, re.DOTALL)
            if res:
                details['audio']['rtpmap'] = res.group(1)

        return details

    def _get_rtp_info(self, reply):
        res = re.match(r'.+?\r\n(RTP-Info: .+?)\r\n', reply, re.DOTALL)
        if not res:
            raise RuntimeError('Invalid RTP-Info')
        rtp_info = res.group(1)

        seq = re.findall(r';seq=(\d+)', rtp_info)
        rtptime = re.findall(r';rtptime=(\d+)', rtp_info)
        if not seq or not rtptime:
            raise RuntimeError('Invalid RTP-Info')

        return {'seq': seq, 'rtptime': rtptime, 'starttime': time.time()}

    def _get_track_ids(self, reply):
        track_ids = re.findall(r'\na=control:.*?(track.*?\d)', reply, re.DOTALL)
        if not track_ids:
            raise RuntimeError('Invalid track ID in reply')
        return track_ids

    def _get_session_id(self, reply):
        res = re.match(r'.+?\nSession: *([^;]+)', reply, re.DOTALL)
        if not res:
            raise RuntimeError('Invalid session ID')
        return res.group(1)

    def _get_self_udp_ports(self):
        start_port = Config.start_udp_port
        idx = list(Config.cameras.keys()).index(self.hash) * 4
        return {
            'track1': [start_port + idx, start_port + idx + 1],
            'track2': [start_port + idx + 2, start_port + idx + 3]}

    def _parse_url(self, url):
        parsed_url = re.match(r'(rtsps?)://(.+?):([^@]+)@(.+?):(\d+)(.+)', url)
        if not parsed_url or len(parsed_url.groups()) != 6:
            raise RuntimeError('Invalid rtsp url')
        return {
            'login': parsed_url.group(2),
            'password': parsed_url.group(3),
            'host': parsed_url.group(4),
            'tcp_port': int(parsed_url.group(5)),
            'url': url.replace(f'{parsed_url.group(2)}:{parsed_url.group(3)}@', '')}

    async def _start_server(self, track_id):
        loop = asyncio.get_running_loop()

        await loop.create_datagram_endpoint(
            lambda: CameraUdpProtocol(self.hash, track_id),
            local_addr=('0.0.0.0', self.udp_ports[track_id][0]))


class CameraUdpProtocol(asyncio.DatagramProtocol):
    def __init__(self, hash, track_id):
        self.hash = hash
        self.track_id = track_id

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if not Shared.data[self.hash]['clients']:
            return

        for _sid, client in Shared.data[self.hash]['clients'].items():
            self.transport.sendto(data, (client['host'], client['ports'][self.track_id][0]))