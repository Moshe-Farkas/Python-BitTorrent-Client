class Piece:

    def __init__(self, index, piece_length):
        self.downloaded_blocks = bytearray()
        self.index = index
        self.piece_length = piece_length

    def next_block(self):
        """
        :return: tuple: (piece-index, byte-offset, length)
            length is PIECE_LENGTH - offset and is capped at 2^14
        """
        length = self.piece_length - self._current_byte_offset()
        if length > 2 ** 14:
            length = 2 ** 14

        # assert self._current_byte_offset() + length <= self.PIECE_LENGTH
        return self.index, self._current_byte_offset(), length

    def _current_byte_offset(self):
        return len(self.downloaded_blocks)

    def put_data(self, data):
        if self._current_byte_offset() + len(data) > self.piece_length:
            return
        # assert self._current_byte_offset() + len(data) <= self.PIECE_LENGTH
        self.downloaded_blocks.extend(data)

    def complete(self):
        return len(self.downloaded_blocks) == self.piece_length

    def dump(self):
        return self.downloaded_blocks
