import os
import sys

from bcoding import bdecode, bencode
from hashlib import sha1
import time
from piece import Piece


class Torrent:

    REQUEST_SIZE = 2 ** 14

    def __init__(self, file_path):
        self.info_hash: bytes = b''
        self.file_length: int = 0
        self.tracker_base_url: str = ''
        self.piece_size: int = 0
        self.piece_hashes = []
        self.my_peer_id: bytes = b''
        self.num_of_pieces = 0
        self._init_torrent_info(file_path)
        self._pieces = self._gen_pieces()
        self._completed_pieces = []
        self._in_progress_pieces = []

        self.temp_peers = []
        self.got_piece = False

    def get_new_piece(self, have_bitfield):
        for index in range(len(have_bitfield)):
            if index in self._in_progress_pieces or index in self._completed_pieces:
                continue
            self._in_progress_pieces.append(index)
            return self._pieces[index]
        return None

    def on_piece_complete(self, index):
        self._completed_pieces.append(index)

    def _init_torrent_info(self, file_path):
        if not file_path.endswith('.torrent'):
            raise ValueError('non valid torrent file')
        with open(file_path, 'rb') as torrent_file:
            decoded_data = bdecode(torrent_file)
        # todo temp remove
        if 'files' in decoded_data['info']:
            print('torrent file is in multi-file mode')
            exit(0)

        self.my_peer_id = sha1(str(time.time()).encode('utf-8')).digest()
        self.tracker_base_url = decoded_data['announce']
        self.file_size = decoded_data['info']['length']
        self.piece_length = decoded_data['info']['piece length']
        self.piece_hashes = self._parse_piece_hashes(decoded_data['info']['pieces'])
        self.info_hash = sha1(bencode(decoded_data['info'])).digest()
        self.num_of_pieces = self.file_size / self.piece_length

    def _parse_piece_hashes(self, concatenated_pieces_hashes):
        return [concatenated_pieces_hashes[i: i + 20] for i in range(0, len(concatenated_pieces_hashes), 20)]

    def _gen_pieces(self):
        pieces = []
        for i in range(int(self.num_of_pieces)):
            pieces.append(Piece(i))
        return pieces

    def temp_print_torrent_info(self):
        print('file length: ', self.file_size)
        print('tracker base url: ', self.tracker_base_url)
        print('piece length: ', self.piece_length)
        print('peer id: ', self.my_peer_id)
        print('info hash: ', self.info_hash)
        print('num of pieces: ', self.num_of_pieces)

    def print_peers(self):
        dumb_count = 0
        unchoked_count = 0
        os.system('cls')
        peer_id = 0
        for peer in self.temp_peers:
            if dumb_count % 3 == 0:
                print()
                dumb_count = 0

            dumb_count += 1

            spaces = 35 - len(peer.current_state)
            unchoked_count += 1 if not peer.choked else 0
            print(f'{peer_id}:  {peer.current_state}', end=spaces * ' ')
            peer_id += 1
        print(f'\nnum of unchoked peers {unchoked_count}')

    def temp_add_peer(self, peer):
        self.temp_peers.append(peer)

    def remove_peer(self, peer_to_remove):
        self.temp_peers.remove(peer_to_remove)
