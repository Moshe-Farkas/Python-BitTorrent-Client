import asyncio
import struct
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
            bin='0' * torrent_session.amount_of_pieces
        )
        self.current_piece = None

        # todo debug stuff
        self.last_request_size = 0
        self.last_byte_offset_request = 0

    async def download(self):
        max_retries = 5
        for i in range(max_retries):
            print(f'trying for the {i+1}th time')
            try:
                await self._download()
                break
            except ConnectionError:
                pass
            except TimeoutError:
                pass

        self._handle_piece_put_back()
        self.torrent_session.remove_peer(self)

    async def _download(self):
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.ip, self.port),
            timeout=10
        )

        handshake = self.torrent_session.handshake()
        writer.write(handshake)
        await writer.drain()

        received_handshake = await asyncio.wait_for(
            reader.read(68),
            timeout=10
        )
        # TODO validate handshake

        await self.send_interested(writer)

        while not self.torrent_session.complete():
            # TODO change from reader.read to wait_for and add a timeout
            buff = await asyncio.wait_for(
                reader.read(4),
                timeout=10
            )
            if not buff or len(buff) != 4:
                self._handle_piece_put_back()
                return
            length = struct.unpack('>I', buff)[0]
            message = b''
            while len(message) < length:
                message += await asyncio.wait_for(
                    reader.read(length - len(message)),
                    timeout=10
                )

            if length == 0:
                continue

            msg_id = struct.unpack('>b', message[:1])[0]

            if msg_id == 0:
                self.choked = True
                self._handle_piece_put_back()
                continue
            elif msg_id == 1:

                self.choked = False

                await self.send_interested(writer)
            elif msg_id == 2 or msg_id == 3:
                continue
            elif msg_id == 4:
                if len(message[1:]) != 4:
                    continue
                have_piece_index = struct.unpack('>I', message[1:])[0]

                self.bitfield[have_piece_index] = True

            elif msg_id == 5:
                self._set_bitfield(bitstring.BitArray(message[1: length]))
            elif msg_id == 7:
                piece_index = struct.unpack('>I', message[1:5])[0]
                self.outbound_requests -= 1
                block_byte_offset = struct.unpack('>I', message[5:9])[0]

                # assert self.last_byte_offset_request == block_byte_offset
                # assert self.last_request_size == len(message[9:])

                if self.last_request_size != len(message[9:]):
                    # logging.error(f'piece index {piece_index}')
                    # logging.error(f'requested block size {self.last_request_size}. got {len(message[9:])}\n')
                    continue

                if self.last_byte_offset_request != block_byte_offset:
                    # logging.error(f'piece index {piece_index}')
                    # logging.error(f'requested byte offset {self.last_byte_offset_request} and got {block_byte_offset}\n')
                    continue

                self.current_piece.put_data(message[9:])

            if not self.choked:
                await self.request_piece(writer)

        writer.close()
        await writer.wait_closed()
        self._handle_piece_put_back()
        self.torrent_session.remove_peer(self)

    async def send_interested(self, writer):
        msg = struct.pack('>Ib', 1, 2)
        writer.write(msg)
        await writer.drain()

    async def request_piece(self, writer):
        if self.outbound_requests > 1:
            return
        if not self.current_piece:
            self.current_piece = self.torrent_session.fetch_work(self.bitfield)
            if not self.current_piece:
                return

        if self.current_piece.complete():
            await self.send_interested(writer)
            await self.torrent_session.on_piece_complete(self.current_piece.index)
            self.current_piece = self.torrent_session.fetch_work(self.bitfield)
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

    def _set_bitfield(self, bitfield):
        self.bitfield = bitfield if len(bitfield) > 0 else self.bitfield

    def _handle_piece_put_back(self):
        if self.current_piece and not self.current_piece.complete():
            self.torrent_session.requeue_piece(self.current_piece.index)
