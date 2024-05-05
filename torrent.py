from hashlib import sha1
import time
from bencode import bencode, bdecode
import bencodepy


class Torrent:

    def __init__(self, file_path):
        self.info_hash: bytes = b''
        self.tracker_urls = []
        self.piece_length: int = 0
        self.total_torrent_length: int
        self.piece_hashes = []
        self.my_peer_id: bytes = b''
        self.amount_of_pieces = 0
        self.files_info = []  # list of dicts: {name: str, length: int)
        self._load_torrent_info(file_path)
    
    def _bad_torrent_file(self, reason: str):
        print("Faulty torrent file provided. Reason:")
        print('\033[91m\t' + reason + '\033[0m')
        exit(0)

    def _load_torrent_info(self, file_path):
        if not file_path.endswith('.torrent'):
            self._bad_torrent_file('file provided does not end in .torrent')
        with open(file_path, 'rb') as torrent_file:
            try:
                decoded_data = bdecode(torrent_file.read())
            except bencodepy.exceptions.BencodeDecodeError:
                self._bad_torrent_file('Torrent file must be encoded using the bencoding format.')

        if 'info' not in decoded_data:
            self._bad_torrent_file('torrent file provided does not contain the info dictionary.')
        if 'announce' not in decoded_data:
            self._bad_torrent_file('torrent file does not contain any trackers')

        self._load_piece_length(decoded_data['info'])
        self._load_tracker_url(decoded_data)
        self._load_files_info_dict(decoded_data['info'])
        self._load_total_torrent_size()
        self._load_piece_hashes(decoded_data['info'])
        self._load_pieces_amount()
        self._set_info_hash(decoded_data['info'])
        self._set_peer_id()

    def _load_piece_length(self, info_dict):
        if 'piece length' not in info_dict:
            self._bad_torrent_file('info dict does not contain piece length.')
        self.piece_length = info_dict['piece length']

    def _load_files_info_dict(self, info_dict):
        if 'files' not in info_dict:
            single_file_info = {
                'length': info_dict['length'],
                'path': info_dict['name'],
            }
            self.files_info = [single_file_info]
            return
        files_info = []
        file_paths = self._parse_file_paths(info_dict)
        absolute_file_offset = 0
        for file_path, file_info_dict in zip(file_paths, info_dict['files']):
            file_length = file_info_dict['length']
            file_info = {
                'length': file_length,
                'path': file_path,
            }
            absolute_file_offset += file_length
            files_info.append(file_info)
        self.files_info = files_info

    def _load_total_torrent_size(self):
        # assumes the torrent file(s) info were already loaded
        # total_torrent_length is the sum of the size of all the files in bytes
        self.total_torrent_length = sum([file_info['length'] for file_info in self.files_info])

    def _load_tracker_url(self, decoded_torrent_file_data):
        self.tracker_urls = []
        self.tracker_urls.append(decoded_torrent_file_data['announce'])
        # many times a torrent file will contain a list of trackers
        # but this is optional
        if 'announce-list' in decoded_torrent_file_data:
            for url in decoded_torrent_file_data['announce-list']:
                self.tracker_urls.append(url[0])

    def _set_info_hash(self, info_dict):
        self.info_hash = sha1(bencode(info_dict)).digest()

    def _load_pieces_amount(self):
        self.amount_of_pieces = len(self.piece_hashes)
    
    def _set_peer_id(self):
        # random 20 byte string
        self.my_peer_id = sha1(str(time.time()).encode('utf-8')).digest()

    def _load_piece_hashes(self, info_dict):
        if 'pieces' not in info_dict:
            self._bad_torrent_file('info dict does not contain the piece hashes.')
        concatenated_piece_hashes = info_dict['pieces']
        hash_len = 20
        self.piece_hashes = [concatenated_piece_hashes[i: i + hash_len] for i in range(0, len(concatenated_piece_hashes), hash_len)]

    def _parse_piece_hashes(self, concatenated_pieces_hashes):
        return [concatenated_pieces_hashes[i: i + 20] for i in range(0, len(concatenated_pieces_hashes), 20)]

    def _parse_file_paths(self, info_dict):
        file_paths = []
        root_dir = info_dict['name']
        for file in info_dict['files']:
            file_path = root_dir
            for path in file['path']:
                file_path += '/' + path
            file_paths.append(file_path)
        return file_paths

    def print_torrent_info(self):
        print('info hash: ', self.info_hash)
        print('trackers found in torrent file : ', self.tracker_urls)
        print('piece length: ', self.piece_length)
        print('peer id: ', self.my_peer_id)
        print('amount of pieces: ', self.amount_of_pieces)
        print('total file(s) length: ', self.total_torrent_length)
        for file in self.files_info:
            print(file['path'], file['length'], 'B')
        print(100*'-', '\n')
