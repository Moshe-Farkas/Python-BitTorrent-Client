import asyncio
import sys
import requests
from peer import Peer
from torrent import Torrent
import urllib.parse
from bcoding import bdecode
from file_saver import FileSaver
from piece import Piece
from hashlib import sha1


class TorrentSession:
    def __init__(self, torrent_info: Torrent):
        self._torrent_info = torrent_info
        self._completed_pieces = 0
        self._seeds = 0
        self._currently_downloading_peers = []  # list of {'ip': , 'port: }
        self.amount_of_pieces = torrent_info.amount_of_pieces
        self._unfinished_pieces = self._gen_pieces()
        self._in_progress_pieces = set()
        self.file_saver = FileSaver(self._torrent_info.torrent_name, self._torrent_info.amount_of_pieces)
        # todo move to tracker obj
        self.request_interval: int

    def _gen_pieces(self):
        pieces = {}
        for i in range(self.amount_of_pieces - 1):
            pieces[i] = Piece(i, self._torrent_info.piece_size)

        last_piece_size = self._torrent_info.file_size - (self.amount_of_pieces - 1) * self._torrent_info.piece_size
        pieces[self.amount_of_pieces - 1] = Piece(self.amount_of_pieces - 1, last_piece_size)

        return pieces

    async def start_session(self):
        asyncio.ensure_future(self.file_saver.start())
        while not self.complete():
            peers = self.tracker_response()
            # TODO choose only peers that are not currently downloading from
            self._start_peer_coros(peers)
            await asyncio.sleep(self.request_interval)

    def complete(self):
        return self._completed_pieces == self._torrent_info.amount_of_pieces

    def _start_peer_coros(self, peer_infos):
        for peer_info in peer_infos:
            peer_obj = Peer(peer_info['ip'], peer_info['port'], self)
            asyncio.ensure_future(peer_obj.download())
            self._currently_downloading_peers.append(peer_obj)

    def handshake(self):
        return chr(19).encode()\
            + b'BitTorrent protocol' \
            + bytes(8) \
            + self._torrent_info.info_hash \
            + self._torrent_info.my_peer_id

    def remove_peer(self, peer):
        try:
            self._currently_downloading_peers.remove(peer)
        except ValueError:
            raise ValueError('what???')

    def fetch_work(self, bitfield):
        # index = 1537
        # if index in self._in_progress_pieces or index not in self._unfinished_pieces and bitfield[index]:
        #     return None
        # self._in_progress_pieces.add(index)
        # return self._unfinished_pieces[index]
        for index, piece in self._unfinished_pieces.items():
            if index not in self._in_progress_pieces and bitfield[index]:
                self._in_progress_pieces.add(index)
                return piece
        return None

    def requeue_piece(self, piece_index):
        self._in_progress_pieces.remove(piece_index)

    async def on_piece_complete(self, piece_index):
        self._completed_pieces += 1
        print(f'completed piece index {piece_index} --- ({self._completed_pieces}/{self.amount_of_pieces})' +
              f' ({round((self._completed_pieces / self.amount_of_pieces) * 100, 2)})')
        # todo handle properly
        piece_hash = sha1(self._unfinished_pieces[piece_index].downloaded_blocks).digest()
        assert piece_hash == self._torrent_info.piece_hashes[piece_index]

        self._in_progress_pieces.remove(piece_index)
        await self.file_saver.put_piece(self._unfinished_pieces[piece_index])

        del self._unfinished_pieces[piece_index]

    #TODO delagte to tracker object
    def tracker_response(self):
        port = 6881
        params = {
            'info_hash': self._torrent_info.info_hash,
            'peer_id': self._torrent_info.my_peer_id,
            'port': port,
            'uploaded': 0,
            'downloaded': 0,
            'left': self._torrent_info.file_size
        }
        url = self._torrent_info.tracker_base_url + '?' + urllib.parse.urlencode(params)
        encoded_response = requests.get(url)
        decoded_response = bdecode(encoded_response.content)
        if 'complete' in decoded_response:
            self._seeds += decoded_response['complete']
        self.request_interval = decoded_response['interval']
        return decoded_response['peers']

    # def multi_file_mode(self, decoded_data):
    #     self.tracker_base_url = decoded_data['announce']
    #     self.my_peer_id = sha1(str(time.time()).encode('utf-8')).digest()
    #     self.file_size = decoded_data['info']['files'][0]['length']   # fg-01
    #     self.piece_length = decoded_data['info']['piece length']
    #     self.piece_hashes = self._parse_piece_hashes(decoded_data['info']['pieces'])
    #     self.info_hash = sha1(bencode(decoded_data['info'])).digest()
    #     self.amount_of_pieces = ceil(self.file_size / self.piece_length)
    #

    # def print_peers(self):
    #     dumb_count = 0
    #     os.system('cls')
    #     peer_id = 0
    #     for peer in self.temp_peers:
    #         if dumb_count % 3 == 0:
    #             print()
    #             dumb_count = 0
    #
    #         dumb_count += 1
    #
    #         spaces = 55 - len(peer.current_state)
    #         print(f'{peer_id}:  {peer.current_state}', end=spaces * ' ')
    #         peer_id += 1
    #     print(f'\ncompleted pieces: {self.completed_count}')
    #
    # def temp_add_peer(self, peer):
    #     self.temp_peers.append(peer)
    #
    # def remove_peer(self, peer_to_remove):
    #     self.temp_peers.remove(peer_to_remove)
