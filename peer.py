import asyncio
import os
import struct
import sys
import time
from enum import Enum
from piece import Piece
import bitstring


class Peer:
    def __init__(self, ip, port, torrent):
        self.torrent = torrent
        self.ip = ip
        self.port = port
        self.outbound_requests = 0
        self.choked = True
        self.bitfield = bitstring.BitArray(
            bin='0' * int(torrent.num_of_pieces)
        )
        self.current_piece = None

        # todo debug stuff
        self.current_state = ''
        self.interested_count = 0

    def make_handshake(self):
        return chr(19).encode() + b'BitTorrent protocol' + bytes(8) + self.torrent.info_hash + self.torrent.my_peer_id

    async def download(self):
        try:
            await self._download()
        except ConnectionError:

            await self.print_peers("couldn't connect")

            self.torrent.remove_peer(self)
            return
        except TimeoutError:

            await self.print_peers("timed out")

            self.torrent.remove_peer(self)
            return

    async def _download(self):
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.ip, self.port),
            timeout=10
        )

        handshake = self.make_handshake()
        writer.write(handshake)
        await writer.drain()

        await self.print_peers('sent handshake')

        received_handshake = await reader.read(68)

        await self.send_interested(writer)

        while True:
            length = await reader.read(4)
            if not length or len(length) != 4:
                await self.print_peers('killed connection')
                self.torrent.remove_peer(self)
                break
            length = struct.unpack('>I', length)[0]
            if length == 0:
                # keep alive
                await self.print_peers('keep alive')

                continue
            message = await reader.read(length)
            if not message:

                await self.print_peers('killed connection')

                self.torrent.remove_peer(self)
                break

            msg_id = struct.unpack('>b', message[:1])[0]

            if msg_id == 0:
                self.choked = True

                await self.print_peers('choked')

                continue
            elif msg_id == 1:

                self.choked = False

                await self.print_peers('un-choked')

            elif msg_id == 2:
                await self.send_unchoke(writer)
            elif msg_id == 3:
                continue
            elif msg_id == 4:
                if len(message[1:]) != 4:
                    continue
                have_piece_index = struct.unpack('>I', message[1:])[0]
                self.bitfield[have_piece_index] = True

                await self.print_peers(f'got have piece ({have_piece_index})')

                # await self.send_interested(writer)

            elif msg_id == 5:
                await self.print_peers(f'got a bitfield')

                self._set_bitfield(bitstring.BitArray(message[1: length]))
                # await self.send_interested(writer)
            elif msg_id == 7:
                piece_index = struct.unpack('>I', message[1:5])[0]
                self.outbound_requests -= 1
                self.torrent.got_piece = True

                await self.print_peers(f'got block in index {piece_index}')

            if not self.choked:
                await self.request_piece(writer)

    async def send_unchoke(self, writer):
        msg = struct.pack('>Ib', 1, 1)
        writer.write(msg)
        await writer.drain()

    async def send_interested(self, writer):
        msg = struct.pack('>Ib', 1, 2)
        writer.write(msg)

        self.interested_count += 1

        await self.print_peers('sending interested')

        await writer.drain()

    async def request_piece(self, writer):
        if self.outbound_requests > 1:
            return
        if not self.current_piece:
            self.current_piece = self.torrent.get_new_piece(self.bitfield)
            if not self.current_piece:
                return

        request_msg = struct.pack(
            '>IbIII',
            13,
            6,
            self.current_piece.index,
            self.current_piece.get_current_byte_offset(),
            self.torrent.REQUEST_SIZE
        )

        await self.print_peers(f'requesting piece index {self.current_piece.index}')

        writer.write(request_msg)
        self.outbound_requests += 1
        await writer.drain()

    def _set_bitfield(self, bitfield):
        self.bitfield = bitfield if len(bitfield) > 0 else self.bitfield

    async def print_peers(self, state):
        await asyncio.sleep(0.4)
        self.current_state = state
        self.torrent.print_peers()
