from bcoding import bdecode, bencode
from hashlib import sha1
import time
import os


class Torrent:

    def __init__(self, file_path):
        self.info_hash: bytes = b''
        self.tracker_base_url: str = ''
        self.piece_length: int = 0
        self.total_torrent_length: int
        self.piece_hashes = []
        self.my_peer_id: bytes = b''
        self.amount_of_pieces = 0
        self.files_info = []  # list of dicts: {name: str, length: int)
        self._init_torrent_info(file_path)
        self.temp_print_torrent_info()

    def _init_torrent_info(self, file_path):
        if not file_path.endswith('.torrent'):
            raise ValueError('non valid torrent file')
        with open(file_path, 'rb') as torrent_file:
            decoded_data = bdecode(torrent_file)
        self.piece_length = decoded_data['info']['piece length']
        self.files_info = self.init_files(decoded_data['info'])
        self.total_torrent_length = sum([file_info['length'] for file_info in self.files_info])
        self._create_folders()
        self.tracker_base_url = decoded_data['announce']
        self.my_peer_id = sha1(str(time.time()).encode('utf-8')).digest()
        self.piece_hashes = self._parse_piece_hashes(decoded_data['info']['pieces'])
        self.amount_of_pieces = len(self.piece_hashes)
        self.info_hash = sha1(bencode(decoded_data['info'])).digest()

    def init_files(self, info_dict):
        if 'files' not in info_dict:
            single_file_info = {
                'length': info_dict['length'],
                'path': info_dict['name'],
                'offset': 0
            }
            return [single_file_info]
        files_info = []
        file_paths = self.parse_file_paths(info_dict)
        absolute_file_offset = 0
        for file_path, file_info_dict in zip(file_paths, info_dict['files']):
            file_length = file_info_dict['length']
            file_info = {
                'length': file_length,
                'path': file_path,
                'offset': absolute_file_offset
            }
            absolute_file_offset += file_length
            files_info.append(file_info)
        return files_info

    def _parse_piece_hashes(self, concatenated_pieces_hashes):
        return [concatenated_pieces_hashes[i: i + 20] for i in range(0, len(concatenated_pieces_hashes), 20)]

    def parse_file_paths(self, info_dict):
        file_paths = []
        root_dir = info_dict['name']
        for file in info_dict['files']:
            file_path = root_dir
            for path in file['path']:
                file_path += '/' + path
            file_paths.append(file_path)
        return file_paths

    def _create_folders(self):
        file_paths = [file_path['path'] for file_path in self.files_info]
        if len(file_paths) == 1:
            return
        for file_path in file_paths:
            dirs = os.path.dirname(file_path).split('/')
            path = ''
            for directory in dirs:
                path += directory
                if not os.path.exists(path):
                    os.mkdir(path)
                path += '/'

    def temp_print_torrent_info(self):
        print('info hash: ', self.info_hash)
        print('tracker base url: ', self.tracker_base_url)
        print('piece size: ', self.piece_length)
        print('peer id: ', self.my_peer_id)
        print('amount of pieces: ', self.amount_of_pieces)
        print(100*'-', '\n')
