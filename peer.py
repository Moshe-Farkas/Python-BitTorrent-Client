import asyncio
import os
import struct
import sys
import time
from enum import Enum
from piece import Piece
import bitstring

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class Peer:
    def __init__(self, ip, port, torrent_session):
        self.torrent_session = torrent_session
        self.ip = ip
        self.port = port
        self.outbound_requests = 0
        self.choked = True
        self.bitfield = bitstring.BitArray(
            bin='0' * torrent_session.num_of_pieces
        )
        self.current_piece = None

        # todo debug stuff
        self.current_state = ''
        self.last_request_size = 0
        self.last_byte_offset_request = 0

    # def make_handshake(self):
    #     return chr(19).encode() + b'BitTorrent protocol' + bytes(8) + self.torrent.info_hash + self.torrent.my_peer_id

    async def download(self):
        self.current_state = 'waiting to connect'
        try:
            await self._download()
        except ConnectionError:
            await self.print_peers("couldn't connect")
            self._handle_piece_put_back()
            self.torrent_session.remove_peer(self)
            return
        except TimeoutError:

            await self.print_peers("timed out")
            self.torrent_session.remove_peer(self)
            return

    async def _download(self):
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.ip, self.port),
            timeout=10
        )

        handshake = self.torrent_session.handshake()
        writer.write(handshake)
        await writer.drain()

        await self.print_peers('sent handshake')

        received_handshake = await reader.read(68)
        # TODO validate handshake

        await self.send_interested(writer)

        while True:
            # TODO change from reader.read to wait_for and add a timeout
            buff = await reader.read(4)
            if not buff or len(buff) != 4:
                self._handle_piece_put_back()
                return
            length = struct.unpack('>I', buff)[0]
            message = b''
            while len(message) < length:
                message += await reader.read(length - len(message))

            assert len(message) == length

            if length == 0:
                await self.print_peers('keep alive')
                continue

            msg_id = struct.unpack('>b', message[:1])[0]

            if msg_id == 0:
                self.choked = True
                self._handle_piece_put_back()
                await self.print_peers('choked')
                continue
            elif msg_id == 1:

                self.choked = False

                await self.print_peers('un-choked')

                await self.send_interested(writer)
            elif msg_id == 2 or msg_id == 3:
                continue
            elif msg_id == 4:
                if len(message[1:]) != 4:
                    continue
                have_piece_index = struct.unpack('>I', message[1:])[0]

                # todo proper handle
                # if have_piece_index < 0 or have_piece_index >= len(self.bitfield):
                #     return
                self.bitfield[have_piece_index] = True

                await self.print_peers(f'got have piece ({have_piece_index})')

            elif msg_id == 5:
                await self.print_peers(f'got a bitfield')

                self._set_bitfield(bitstring.BitArray(message[1: length]))
            elif msg_id == 7:
                piece_index = struct.unpack('>I', message[1:5])[0]
                self.outbound_requests -= 1
                block_byte_offset = struct.unpack('>I', message[5:9])[0]

                await self.print_peers(f'index: {piece_index} got byte offset of {block_byte_offset} when requested {self.last_byte_offset_request}')

                # assert self.last_byte_offset_request == block_byte_offset
                # assert self.last_request_size == len(message[9:])

                if self.last_request_size != len(message[9:]):
                    logging.error(f'piece index {piece_index}')
                    logging.error(f'requested block size {self.last_request_size}. got {len(message[9:])}\n')
                    continue

                if self.last_byte_offset_request != block_byte_offset:
                    logging.error(f'piece index {piece_index}')
                    logging.error(f'requested byte offset {self.last_byte_offset_request} and got {block_byte_offset}\n')
                    continue

                self.current_piece.put_data(message[9:])

            if not self.choked:
                await self.request_piece(writer)

    async def send_interested(self, writer):
        msg = struct.pack('>Ib', 1, 2)
        writer.write(msg)
        await writer.drain()

        await self.print_peers('sent interested')

    async def request_piece(self, writer):
        if self.outbound_requests > 1:
            return
        if not self.current_piece:
            self.current_piece = self.torrent_session.dequeue_piece(self.bitfield)
            if not self.current_piece:
                return

        if self.current_piece.complete():
            await self.send_interested(writer)
            await self.torrent_session.on_piece_complete(self.current_piece.index)
            print(f'from peer: {self.ip}\n')
            self.current_piece = self.torrent_session.dequeue_piece(self.bitfield)
            if not self.current_piece:
                return

        current_piece_index, byte_offset, length = self.current_piece.next_block()

        request_msg = struct.pack(
            '>IbIII',
            13,
            6,
            current_piece_index,
            byte_offset,
            length
        )

        self.last_request_size = length
        self.last_byte_offset_request = byte_offset

        writer.write(request_msg)
        self.outbound_requests += 1
        await writer.drain()

        await self.print_peers(f'requesting index: {current_piece_index}, offset {byte_offset}, length {length}')

    def _set_bitfield(self, bitfield):
        self.bitfield = bitfield if len(bitfield) > 0 else self.bitfield

    def _handle_piece_put_back(self):
        if self.current_piece:
            self.torrent_session.requeue_piece(self.current_piece.index)

    async def print_peers(self, state):
        # await asyncio.sleep(1)
        self.current_state = state
        # self.torrent.print_peers()



