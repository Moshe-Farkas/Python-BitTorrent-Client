import asyncio
import os
import struct
import sys
import requests
from peer import Peer
from torrent import Torrent
import urllib.parse
from bcoding import bdecode
from file_saver import FileSaver
from piece import Piece
from hashlib import sha1
import socket
import random


class TorrentSession:
    def temp_missing_pieces(self):
        unfinished = []
        for i in range(self.amount_of_pieces):
            if not os.path.exists(f'{self.parts_folder_name}/.{i}'):
                unfinished.append(i)

        print('unfinished pieces: ', unfinished)

    def __init__(self, torrent_info: Torrent):
        self._torrent_info = torrent_info
        self.parts_folder_name = bytes.hex(self._torrent_info.info_hash)
        self._seeds = -1
        self._currently_downloading_peers = []
        self.amount_of_pieces = torrent_info.amount_of_pieces
        self._unfinished_pieces = self._gen_pieces()
        if os.path.exists(self.parts_folder_name):
            self.serialize_saved_pieces()
            self._completed_pieces = self.amount_of_pieces - len(self._unfinished_pieces)
        else:
            self._completed_pieces = 0
            os.mkdir(self.parts_folder_name)
        self._in_progress_pieces = set()
        self.file_saver = FileSaver(self._torrent_info.files_info, self.amount_of_pieces, self.parts_folder_name)

        self.last_piece = -1

    def serialize_saved_pieces(self):
        for i in range(self.amount_of_pieces):
            if os.path.exists(f'{self.parts_folder_name}/.{i}'):
                self._unfinished_pieces.pop(i)

    def _gen_pieces(self):
        pieces = {}
        for i in range(self.amount_of_pieces - 1):
            pieces[i] = Piece(i, self._torrent_info.piece_length)

        last_piece_size = self._torrent_info.total_torrent_length - (self.amount_of_pieces - 1) * self._torrent_info.piece_length
        pieces[self.amount_of_pieces - 1] = Piece(self.amount_of_pieces - 1, last_piece_size)
        return pieces

    async def start_session(self):
        file_saver_task = asyncio.ensure_future(self.file_saver.start())
        peers = self.tracker_response()

        print(f'got {len(peers)} peers')
        peers_coros = []
        for peer in peers:
            ip, port = peer.values()
            peers_coros.append(Peer(ip, port, self).download())

        await asyncio.gather(*peers_coros)
        if not self.complete():
            print('Connection Error. Retry')
            exit(1)
        await file_saver_task
        self.file_saver.assemble_file()

    def complete(self):
        return self._completed_pieces == self._torrent_info.amount_of_pieces

    def handshake(self):
        return chr(19).encode() \
            + b'BitTorrent protocol' \
            + bytes(8) \
            + self._torrent_info.info_hash \
            + self._torrent_info.my_peer_id

    def fetch_work(self, bitfield):
        for index, piece in self._unfinished_pieces.items():
            if index not in self._in_progress_pieces and bitfield[index]:
                self._in_progress_pieces.add(index)
                return piece
        return None

    def requeue_piece(self, piece_index):
        print(f'{20*"#"} putting {piece_index} back in the queue {20*"#"}')
        self._in_progress_pieces.remove(piece_index)

    async def on_piece_complete(self, piece_index):
        piece_hash = sha1(self._unfinished_pieces[piece_index].downloaded_blocks).digest()
        if piece_hash != self._torrent_info.piece_hashes[piece_index]:
            self.requeue_piece(piece_index)
            return

        print(f'completed piece index {piece_index} --- ({self._completed_pieces}/{self.amount_of_pieces})' +
              f' ({round((self._completed_pieces / self.amount_of_pieces) * 100, 2):.2f}%)')
        self._completed_pieces += 1

        self._in_progress_pieces.remove(piece_index)
        await self.file_saver.put_piece(self._unfinished_pieces[piece_index])
        del self._unfinished_pieces[piece_index]

        if self._completed_pieces == self.amount_of_pieces:
            await self.file_saver.put_piece(None)

    def remove_peer(self, peer):
        pass
        # print(f'closing peer {peer.ip}')
        # self._currently_downloading_peers.remove(peer)
        # print(f'peers left: {len(self._currently_downloading_peers)}')

    # TODO delagte to tracker object
    def tracker_response(self):
        total_peers = []
        for url in self._torrent_info.tracker_urls:
            if len(total_peers) >= 50:
                break
            if url.startswith('http'):
                total_peers.extend(self._http_tracker(url))
            elif url.startswith('udp'):
                total_peers.extend(self._udp_tracker(url))
        return total_peers

    def _http_tracker(self, address):
        port = 6881
        params = {
            'info_hash': self._torrent_info.info_hash,
            'peer_id': self._torrent_info.my_peer_id,
            'port': port,
            'uploaded': 0,
            'downloaded': 0,
            'left': self._torrent_info.total_torrent_length
        }
        url = address + '?' + urllib.parse.urlencode(params)
        encoded_response = requests.get(url, timeout=1.0)
        if encoded_response.status_code != 200:
            return []
        decoded_response = bdecode(encoded_response.content)
        if 'complete' in decoded_response:
            self._seeds += decoded_response['complete']
        return decoded_response['peers']

    def _udp_tracker(self, url):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.0)
        connect_message = self.build_udp_connect_request()
        parsed_url = urllib.parse.urlparse(url)
        # udp://tracker.torrent.eu.org:451/announce
        try:
            sock.sendto(connect_message, (parsed_url.hostname, parsed_url.port))
            response = sock.recv(16)
            connection_id = self.parse_udp_connect_response(response)
            announce_request = self.build_udp_announce_request(connection_id)
            sock.sendto(announce_request, (parsed_url.hostname, parsed_url.port))
            response = sock.recv(4096)
            return self.parse_udp_announce_response(response)
        except ConnectionError:
            return []
        except TimeoutError:
            return []
        except socket.gaierror:
            return []

    def build_udp_connect_request(self):
        # Offset  Size            Name            Value
        # 0       64-bit integer  connection_id   0x41727101980
        # 8       32-bit integer  action          0 // connect
        # 12      32-bit integer  transaction_id  ? // random
        # 16
        protocol_id = struct.pack('>Q', 0x41727101980)
        action = struct.pack('>I', 0)
        transaction_id = bytes(random.getrandbits(8) for _ in range(4))
        return protocol_id + action + transaction_id

    def parse_udp_connect_response(self, message):
        # Offset  Size            Name               Value
        # 0       32-bit integer  action             0 // connect
        # 4       32-bit integer  transaction_id
        # 8      64-bit integer  connection_id
        # 16
        return message[8:]

    def build_udp_announce_request(self, connection_id):
        # Offset  Size    Name    Value
        # 0       64-bit integer  connection_id
        # 8       32-bit integer  action          1 // announce
        # 12      32-bit integer  transaction_id
        # 16      20-byte string  info_hash
        # 36      20-byte string  peer_id
        # 56      64-bit integer  downloaded
        # 64      64-bit integer  left
        # 72      64-bit integer  uploaded
        # 80      32-bit integer  event           0 // 0: none; 1: completed; 2: started; 3: stopped
        # 84      32-bit integer  IP address      0 // default
        # 88      32-bit integer  key             ? // random
        # 92      32-bit integer  num_want        -1 // default
        # 96      16-bit integer  port            ? //
        # 98
        action = struct.pack('>I', 1)
        transaction_id = bytes(random.getrandbits(8) for _ in range(4))
        to_download = self._torrent_info.total_torrent_length - sum([piece.piece_length for piece in self._unfinished_pieces.values()])
        downloaded = struct.pack('>Q', to_download)
        left = struct.pack('>Q', self._torrent_info.total_torrent_length - to_download)
        uploaded = struct.pack('>Q', 0)
        event = struct.pack('>I', 0)
        ip = struct.pack('>I', 0)
        key = bytes(random.getrandbits(8) for _ in range(4))
        want = struct.pack('>i', -1)
        port = struct.pack('>H', 6881)

        return (
                connection_id + action + transaction_id + self._torrent_info.info_hash +
                self._torrent_info.my_peer_id + downloaded + left + uploaded + event +
                ip + key + want + port
        )

    def parse_udp_announce_response(self, response):
        #  Offset      Size            Name            Value
        # 0           32-bit integer  action          1 // announce
        # 4           32-bit integer  transaction_id
        # 8           32-bit integer  interval
        # 12          32-bit integer  leechers
        # 16          32-bit integer  seeders
        # 20 + 6 * n  32-bit integer  IP address
        # 24 + 6 * n  16-bit integer  TCP port
        # 20 + 6 * N

        ips = response[20:]
        peers = []
        for i in range(0, len(ips), 6):
            peer_ip, peer_port = struct.unpack('>IH', ips[i: i+6])
            # peers.append(
            #     {'ip': str(ipaddress.IPv4Address(peer_ip)), 'port': peer_port}
            # )
            peers.append(
                {'ip': socket.inet_ntoa(ips[i: i+4]), 'port': peer_port}
            )
        return peers
