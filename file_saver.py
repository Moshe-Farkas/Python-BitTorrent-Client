import asyncio
import sys

import aiofiles


class FileSaver:
    def __init__(self, file_path, amount_of_pieces):
        self._write_queue = asyncio.Queue()
        self.amount_of_pieces = amount_of_pieces
        self._written_count = 0

    async def put_piece(self, piece):
        await self._write_queue.put(piece)

    async def start(self):
        while self._written_count < self.amount_of_pieces:
            complete_piece = await self._write_queue.get()
            async with aiofiles.open(f'temp-complete-file/_{complete_piece.index}', mode='wb') as piece_file:
                await piece_file.write(complete_piece.dump())
                print(f'wrote piece {complete_piece.index} to disk')
                self._written_count += 1

        self.assemble_parts()

    def assemble_parts(self):
        with open('ubuntu.iso', 'wb') as final_file:
            for i in range(self.amount_of_pieces):
                with open(f'temp-complete-file/_{i}', 'rb') as piece_file:
                    final_file.write(piece_file.read())

