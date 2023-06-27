import asyncio
import aiofiles


class FileSaver:
    def __init__(self, files_info, amount_of_pieces, parts_folder_name):
        self._write_queue = asyncio.Queue()
        self._amount_of_pieces = amount_of_pieces
        self._written_count = 0
        self.parts_folder_name = parts_folder_name
        self.files = self.files_generator([File(info['length'], info['path'], info['offset']) for info in files_info])
        self.current_file: File = next(self.files)

    async def put_piece(self, piece): 
        await self._write_queue.put(piece)

    def files_generator(self, files: list):
        for file in files:
            yield file

    async def start(self):
        while True:
            complete_piece = await self._write_queue.get()
            if complete_piece is None:
                break
            async with aiofiles.open(f'{self.parts_folder_name}/_{complete_piece.index}', mode='wb') as piece_file:
                await piece_file.write(complete_piece.dump())
                print(f'wrote piece {complete_piece.index} to disk')
                self._written_count += 1

        self.assemble_parts()

    def assemble_parts(self):
        print(10*'-', ' assembling file(s) ', 10*'-')

        # with open(self._file_name, 'wb') as final_file:
        #     for i in range(self._amount_of_pieces):
        #         with open(f'{self.parts_folder_name}/_{i}', 'rb') as piece_file:
        #             final_file.write(piece_file.read())
        #             print(f'appended piece {i}')

        for piece_index in range(self._amount_of_pieces):
            with open(f'{self.parts_folder_name}/_{piece_index}', 'rb') as piece_file:
                buffer = piece_file.read()
                while len(buffer) > 0:
                    bytes_left = self.current_file.bytes_left()
                    if bytes_left == 0:
                        try:
                            self.current_file.open_file.close()
                            self.current_file = next(self.files)
                        except StopIteration:
                            break

                    if bytes_left < len(buffer):
                        buffer = buffer[: bytes_left]
                    self.current_file.put_data(buffer)


class File:
    def __init__(self, length, path, offset):
        """
        :param length:
        :param path:
        :param offset: absolute offset within contiguous block of files
        """
        self.length = length
        self.path = path
        self.current_offset = offset
        self.open_file = open(path, mode='wb')

    def bytes_left(self):
        return self.length - self.current_offset

    def put_data(self, buffer):
        """
        assumes buffer is valid length
        :param buffer:
        :return:
        """
        self.open_file.write(buffer)
        self.current_offset += len(buffer)


