import asyncio
import os
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
    def temp_missing_pieces(self):
        unfinished = []
        for i in range(self.amount_of_pieces):
            if not os.path.exists(f'{self.parts_folder_name}/_{i}'):
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
        # todo move to tracker obj
        self.request_interval: int

    def serialize_saved_pieces(self):
        for i in range(self.amount_of_pieces):
            if os.path.exists(f'{self.parts_folder_name}/_{i}'):
                self._unfinished_pieces.pop(i)

    def _gen_pieces(self):
        pieces = {}
        for i in range(self.amount_of_pieces - 1):
            pieces[i] = Piece(i, self._torrent_info.piece_length)

        last_piece_size = self._torrent_info.total_torrent_length - (self.amount_of_pieces - 1) * self._torrent_info.piece_length
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

    def fetch_work(self, bitfield):
        # index = 286
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
              f' ({round((self._completed_pieces / self.amount_of_pieces) * 100, 2)}%) peers left: {len(self._currently_downloading_peers)}')
        # TODO handle properly
        piece_hash = sha1(self._unfinished_pieces[piece_index].downloaded_blocks).digest()
        assert piece_hash == self._torrent_info.piece_hashes[piece_index]

        self._in_progress_pieces.remove(piece_index)
        await self.file_saver.put_piece(self._unfinished_pieces[piece_index])

        del self._unfinished_pieces[piece_index]

    def remove_peer(self, peer):
        print(f'closing peer {peer.ip}')
        self._currently_downloading_peers.remove(peer)
        print(f'peers left: {len(self._currently_downloading_peers)}')

    #TODO delagte to tracker object
    def tracker_response(self):
        port = 6881
        params = {
            'info_hash': self._torrent_info.info_hash,
            'peer_id': self._torrent_info.my_peer_id,
            'port': port,
            'uploaded': 0,
            'downloaded': 0,
            'left': self._torrent_info.total_torrent_length
        }
        url = self._torrent_info.tracker_base_url + '?' + urllib.parse.urlencode(params)
        encoded_response = requests.get(url)
        decoded_response = bdecode(encoded_response.content)
        if 'complete' in decoded_response:
            self._seeds += decoded_response['complete']
        self.request_interval = decoded_response['interval']
        return decoded_response['peers']
