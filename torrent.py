import asyncio
import os
import sys

from bcoding import bdecode, bencode
from hashlib import sha1
import time
from piece import Piece
from math import ceil
from file_saver import FileSaver


class Torrent:

    def __init__(self, file_path):
        self.info_hash: bytes = b''
        self.file_size: int = 0
        self.tracker_base_url: str = ''
        self.piece_length: int = 0
        self.piece_hashes = []
        self.my_peer_id: bytes = b''
        self.num_of_pieces = 0
        self.torrent_name = ''

        self._init_torrent_info(file_path)

    def _init_torrent_info(self, file_path):
        if not file_path.endswith('.torrent'):
            raise ValueError('non valid torrent file')
        with open(file_path, 'rb') as torrent_file:
            decoded_data = bdecode(torrent_file)
        # todo implement
        if 'files' in decoded_data['info']:
            raise NotImplemented

        self.tracker_base_url = decoded_data['announce']

        self.my_peer_id = sha1(str(time.time()).encode('utf-8')).digest()
        self.file_size = decoded_data['info']['length']
        self.piece_length = decoded_data['info']['piece length']
        self.piece_hashes = self._parse_piece_hashes(decoded_data['info']['pieces'])
        self.info_hash = sha1(bencode(decoded_data['info'])).digest()
        self.num_of_pieces = ceil(self.file_size / self.piece_length)
        self.torrent_name = decoded_data['info']['name']

    def _parse_piece_hashes(self, concatenated_pieces_hashes):
        return [concatenated_pieces_hashes[i: i + 20] for i in range(0, len(concatenated_pieces_hashes), 20)]

