import asyncio
import aiofiles
import os
import shutil


class FileSaver:
    def __init__(self, files_info, amount_of_pieces, parts_folder_name):
        self._write_queue = asyncio.Queue()
        self._amount_of_pieces = amount_of_pieces
        self._written_count = 0
        self._create_folders(files_info)
        self.files = self.files_generator([File(file['length'], file['path']) for file in files_info])
        self.current_file = next(self.files)
        self.parts_folder_name = parts_folder_name

    async def put_piece(self, piece): 
        await self._write_queue.put(piece)

    def files_generator(self, files: list):
        for file in files:
            yield file

    async def start(self):
        # self.assemble_parts()
        # return
        while True:
            complete_piece = await self._write_queue.get()
            if complete_piece is None:
                break
            async with aiofiles.open(f'{self.parts_folder_name}/.{complete_piece.index}', mode='wb') as piece_file:
                await piece_file.write(complete_piece.dump())
                print(f'wrote piece {complete_piece.index} to disk')
                self._written_count += 1

    def assemble_file(self):
        self.assemble_parts()
        shutil.rmtree(self.parts_folder_name)

    def assemble_parts(self):
        """
        A piece can belong to more than one file so a piece may need to be broken up and distributed to
        the right file
        :return:
        """
        print(10*'-', ' assembling file(s) ', 10*'-')
        for piece_index in range(self._amount_of_pieces):
            with open(f'{self.parts_folder_name}/.{piece_index}', 'rb') as piece_file:
                buffer = piece_file.read()
                while len(buffer) > 0:
                    bytes_left = self.current_file.bytes_left()
                    if bytes_left == 0:
                        try:
                            self.current_file.open_file.close()
                            self.current_file = next(self.files)
                        except StopIteration:
                            break

                    if len(buffer) > bytes_left:
                        self.current_file.put_data(buffer[:bytes_left])
                        buffer = buffer[bytes_left:]
                    else:
                        self.current_file.put_data(buffer)
                        buffer = []

        self.current_file.open_file.close()

    def _create_folders(self, files_info):
        file_paths = [file['path'] for file in files_info]
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


class File:
    def __init__(self, length, path):
        """
        :param length:
        :param path:
        :param offset: absolute offset within contiguous block of files
        """
        self.length = length
        self.path = path
        self.current_offset = 0
        self.open_file = open(path, mode='wb')

    def bytes_left(self):
        return self.length - self.current_offset

    def put_data(self, buffer):
        """
        assumes buffer is valid length
        :param buffer:
        :return:
        """
        # print('writing to file: ', self.open_file.name, ' and length of: ', len(buffer))

        self.open_file.write(buffer)
        self.current_offset += len(buffer)


