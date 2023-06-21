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

    REQUEST_SIZE = 2 ** 14

    def __init__(self, file_path):
        self.info_hash: bytes = b''
        self.file_size: int = 0
        self.tracker_base_url: str = ''
        self.piece_length: int = 0
        self.piece_hashes = []
        self.my_peer_id: bytes = b''
        self.num_of_pieces = 0
        self._init_torrent_info(file_path)
        self._in_progress_pieces = []
        self._completed_pieces = []
        # todo refactor this into dict to speed up `in` check time
        self._pieces = self._gen_pieces()
        self.file_saver = FileSaver('placeholder', self.num_of_pieces)
        self.temp_peers = []
        self.completed_count = 0

    def get_new_piece(self, have_bitfield):
        # index = 13514
        # if not have_bitfield[index] or index in self._completed_pieces or index in self._in_progress_pieces:
        #     return None
        # self._in_progress_pieces.append(index)
        # return self._pieces[index]

        for index, piece in self._pieces.items():
            if index in self._in_progress_pieces or index in self._completed_pieces:
                continue
            # if index >= len(have_bitfield):
            #     print(f'index {index} out of range of bitfield')
            if have_bitfield[index]:
                self._in_progress_pieces.append(index)
                return piece
        return None

    def put_piece_back(self, index):
        # todo figure out why somtimes index is not in list
        assert index in self._in_progress_pieces

        if index in self._in_progress_pieces:
            self._in_progress_pieces.remove(index)

    async def on_piece_complete(self, index):
        print(f' ---- finished piece {index} ----- ')
        piece_hash = sha1(self._pieces[index].downloaded_blocks).digest()
        print(f'expected hash is {self.piece_hashes[index]}')
        print(f'got {piece_hash}')
        print(f'{round((self.completed_count / self.num_of_pieces) * 100, 2)}% complete')

        self._completed_pieces.append(index)
        self._in_progress_pieces.remove(index)
        self.completed_count += 1
        assert piece_hash == self.piece_hashes[index]
        await self.file_saver.put_piece(self._pieces[index])
        del self._pieces[index]

    def _init_torrent_info(self, file_path):
        if not file_path.endswith('.torrent'):
            raise ValueError('non valid torrent file')
        with open(file_path, 'rb') as torrent_file:
            decoded_data = bdecode(torrent_file)
        # todo implement
        if 'files' in decoded_data['info']:
            self.multi_file_mode(decoded_data)
            return

        self.tracker_base_url = decoded_data['announce']

        self.my_peer_id = sha1(str(time.time()).encode('utf-8')).digest()
        self.file_size = decoded_data['info']['length']
        self.piece_length = decoded_data['info']['piece length']
        self.piece_hashes = self._parse_piece_hashes(decoded_data['info']['pieces'])
        self.info_hash = sha1(bencode(decoded_data['info'])).digest()
        self.num_of_pieces = ceil(self.file_size / self.piece_length)

    def _parse_piece_hashes(self, concatenated_pieces_hashes):
        return [concatenated_pieces_hashes[i: i + 20] for i in range(0, len(concatenated_pieces_hashes), 20)]

    def multi_file_mode(self, decoded_data):
        self.tracker_base_url = decoded_data['announce']
        self.my_peer_id = sha1(str(time.time()).encode('utf-8')).digest()
        self.file_size = decoded_data['info']['files'][0]['length']   # fg-01
        self.piece_length = decoded_data['info']['piece length']
        self.piece_hashes = self._parse_piece_hashes(decoded_data['info']['pieces'])
        self.info_hash = sha1(bencode(decoded_data['info'])).digest()
        self.num_of_pieces = ceil(self.file_size / self.piece_length)

    def _gen_pieces(self):
        pieces = {}
        for i in range(self.num_of_pieces - 1):
            pieces[i] = Piece(i, self.piece_length)

        last_piece_size = self.file_size - (self.num_of_pieces - 1) * self.piece_length
        pieces[self.num_of_pieces-1] = (Piece(self.num_of_pieces-1, last_piece_size))
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
        os.system('cls')
        peer_id = 0
        for peer in self.temp_peers:
            if dumb_count % 3 == 0:
                print()
                dumb_count = 0

            dumb_count += 1

            spaces = 55 - len(peer.current_state)
            print(f'{peer_id}:  {peer.current_state}', end=spaces * ' ')
            peer_id += 1
        print(f'\ncompleted pieces: {self.completed_count}')

    def temp_add_peer(self, peer):
        self.temp_peers.append(peer)

    def remove_peer(self, peer_to_remove):
        self.temp_peers.remove(peer_to_remove)
