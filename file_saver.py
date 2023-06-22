import asyncio
import sys

import aiofiles


class FileSaver:
    def __init__(self, file_name, amount_of_pieces):
        self._write_queue = asyncio.Queue()
        self._amount_of_pieces = amount_of_pieces
        self._written_count = 0
        self._file_name = file_name

    async def put_piece(self, piece):
        await self._write_queue.put(piece)

    async def start(self):
        while self._written_count < self._amount_of_pieces:
            complete_piece = await self._write_queue.get()
            async with aiofiles.open(f'temp-complete-file/_{complete_piece.index}', mode='wb') as piece_file:
                await piece_file.write(complete_piece.dump())
                print(f'wrote piece {complete_piece.index} to disk')
                self._written_count += 1

        self.assemble_parts()

    def assemble_parts(self):
        print(10*'-', ' assembling file ', 10*'-')
        with open('ubuntu.iso', 'wb') as final_file:
            for i in range(self._amount_of_pieces):
                with open(f'temp-complete-file/_{i}', 'rb') as piece_file:
                    final_file.write(piece_file.read())
                    print(f'appended piece {i}')

