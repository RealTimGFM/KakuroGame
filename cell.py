class Cell:
    def __init__(self, position, board):
        self.position = None
        self.board = board
        self.invalid_positions = []
        self.editCell(position)

    def editCell(self, position):
        self.position = int(position)
        return self.position

    def setValue(self, value):
        key = str(self.position)
        if value in (None, ""):
            self.board.pop(key, None)
        else:
            self.board[key] = str(value)
        return self.board

    def highlightCell(self):
        self.invalid_positions = [self.position]
        return self.invalid_positions