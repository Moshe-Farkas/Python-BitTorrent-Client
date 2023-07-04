import asyncio
import os
from peer import Peer
from torrent import Torrent
from file_saver import FileSaver
from piece import Piece
from hashlib import sha1
from tracker import peer_gen


class TorrentSession:
    def __init__(self, torrent_info: Torrent):
        self._torrent_info = torrent_info
        self.info_hash = self._torrent_info.info_hash
        self.parts_folder_name = bytes.hex(self._torrent_info.info_hash)
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
        peer_counter = 0
        peer_tasks = []
        peer_generator = peer_gen(self._torrent_info.tracker_urls, self._torrent_info)
        for peers in peer_generator:
            # each yield returns a response from a url parsed as a list of peers
            if peer_counter >= 50:
                # 50 peers is enough
                break
            peer_counter += len(peers)
            peer_tasks.extend([Peer(peer['ip'], peer['port'], self).download() for peer in peers])

        await asyncio.gather(*peer_tasks)
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

        self._completed_pieces += 1
        print(f'completed piece index {piece_index} --- ({self._completed_pieces}/{self.amount_of_pieces})' +
              f' ({round((self._completed_pieces / self.amount_of_pieces) * 100, 2):.2f}%)')

        self._in_progress_pieces.remove(piece_index)
        await self.file_saver.put_piece(self._unfinished_pieces[piece_index])
        del self._unfinished_pieces[piece_index]

        if self._completed_pieces == self.amount_of_pieces:
            await self.file_saver.put_piece(None)

