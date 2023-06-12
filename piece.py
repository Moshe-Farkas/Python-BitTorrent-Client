class Piece:
    PIECE_LENGTH: int

    def __init__(self, index):
        self._downloaded_blocks = list()
        self.index = index

    def get_current_byte_offset(self):
        return len(self._downloaded_blocks)


class Block:
    pass
