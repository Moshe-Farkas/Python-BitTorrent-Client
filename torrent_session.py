import asyncio
import sys
import requests
from peer import Peer
from torrent import Torrent
import urllib.parse
from bcoding import bdecode
from file_saver import FileSaver


class TorrentSession:
    def __init__(self, torrent_info: Torrent):
        self._torrent_info = torrent_info
        self._completed_pieces = 0
        self._seeds = 0
        self._currently_downloading_peers = []  # list of {'ip': , 'port: }
        self.num_of_pieces = torrent_info.num_of_pieces

        # todo move to tracker obj
        self.request_interval: int

    async def start_session(self):
        file_saver = FileSaver(self._torrent_info.torrent_name, self._torrent_info.num_of_pieces)
        asyncio.ensure_future(file_saver.start())
        while not self.complete():
            # get_tracker_response()
            # sift through peers and choose only the ones not in currently downloading list
            # run_coros(response.peers) # non blocking. needs to add new peers only
            # await sleep(interval_time)

            peers = self.tracker_response()
            # TODO choose only peers that are not currently downloading from
            self._start_peer_coros(peers)
            await asyncio.sleep(self.request_interval)

    def complete(self):
        return self._completed_pieces == self._torrent_info.num_of_pieces

    def _start_peer_coros(self, peer_infos):
        for peer_info in peer_infos:
            peer_obj = Peer(peer_info['ip'], peer_info['port'], self)
            asyncio.ensure_future(peer_obj.download())
            self._currently_downloading_peers.append(peer_info)

    def handshake(self):
        return chr(19).encode()\
            + b'BitTorrent protocol' \
            + bytes(8) \
            + self._torrent_info.info_hash \
            + self._torrent_info.my_peer_id

    def remove_peer(self, peer):
        pass

    def dequeue_piece(self, bitfield):
        pass

    def requeue_piece(self, piece_index):
        pass

    def on_piece_complete(self, piece_index):
        pass

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
        # complete
        # incomplete
        # interval
        # peers
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
    #     self.num_of_pieces = ceil(self.file_size / self.piece_length)
    #
    # def _gen_pieces(self):
    #     pieces = {}
    #     for i in range(self.num_of_pieces - 1):
    #         pieces[i] = Piece(i, self.piece_length)
    #
    #     last_piece_size = self.file_size - (self.num_of_pieces - 1) * self.piece_length
    #     pieces[self.num_of_pieces-1] = (Piece(self.num_of_pieces-1, last_piece_size))
    #     return pieces
    #
    # def temp_print_torrent_info(self):
    #     print('file length: ', self.file_size)
    #     print('tracker base url: ', self.tracker_base_url)
    #     print('piece length: ', self.piece_length)
    #     print('peer id: ', self.my_peer_id)
    #     print('info hash: ', self.info_hash)
    #     print('num of pieces: ', self.num_of_pieces)
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
    #
    # def get_new_piece(self, have_bitfield):
    #     # index = 13514
    #     # if not have_bitfield[index] or index in self._completed_pieces or index in self._in_progress_pieces:
    #     #     return None
    #     # self._in_progress_pieces.append(index)
    #     # return self._pieces[index]
    #
    #     for index, piece in self._pieces.items():
    #         if index in self._in_progress_pieces or index in self._completed_pieces:
    #             continue
    #         # if index >= len(have_bitfield):
    #         #     print(f'index {index} out of range of bitfield')
    #         if have_bitfield[index]:
    #             self._in_progress_pieces.append(index)
    #             return piece
    #     return None
    #
    # def put_piece_back(self, index):
    #     # todo figure out why somtimes index is not in list
    #     assert index in self._in_progress_pieces
    #
    #     if index in self._in_progress_pieces:
    #         self._in_progress_pieces.remove(index)
    #
    # async def on_piece_complete(self, index):
    #     print(f' ---- finished piece {index} ----- ')
    #     piece_hash = sha1(self._pieces[index].downloaded_blocks).digest()
    #     print(f'expected hash is {self.piece_hashes[index]}')
    #     print(f'got {piece_hash}')
    #     print(f'{round((self.completed_count / self.num_of_pieces) * 100, 2)}% complete')
    #
    #     self._completed_pieces.append(index)
    #     self._in_progress_pieces.remove(index)
    #     self.completed_count += 1
    #     assert piece_hash == self.piece_hashes[index]
    #     await self.file_saver.put_piece(self._pieces[index])
    #     del self._pieces[index]