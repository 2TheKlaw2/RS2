import numpy as np


class Connect4:
    ROWS = 6
    COLS = 7
    EMPTY = 0
    PLAYER_1 = 1
    PLAYER_2 = 2

    def __init__(self):
        self.board = np.zeros((self.ROWS, self.COLS), dtype=int)
        self.current_player = self.PLAYER_1
        self.winner = None
        self.game_over = False

    def reset(self):
        self.board = np.zeros((self.ROWS, self.COLS), dtype=int)
        self.current_player = self.PLAYER_1
        self.winner = None
        self.game_over = False
        return self.get_state()

    def get_state(self):
        return self.board.copy()

    def get_valid_moves(self):
        valid_moves = []
        for col in range(self.COLS):
            if self.board[0][col] == self.EMPTY:
                valid_moves.append(col)
        return valid_moves

    def is_valid_move(self, col):
        return col in self.get_valid_moves()

    def get_next_open_row(self, col):
        for row in range(self.ROWS - 1, -1, -1):
            if self.board[row][col] == self.EMPTY:
                return row
        return None

    def drop_piece(self, col, player=None):
        if self.game_over:
            return False

        if not self.is_valid_move(col):
            return False

        row = self.get_next_open_row(col)
        if row is None:
            return False

        if player is None:
            player = self.current_player

        self.board[row][col] = player

        if self.check_win(player):
            self.winner = player
            self.game_over = True
        elif self.is_draw():
            self.winner = 0
            self.game_over = True
        else:
            if player == self.current_player:
                self.switch_player()

        return True

    def step(self, col):
        if self.game_over:
            return self.get_state(), 0, True

        valid_move = self.drop_piece(col)

        if not valid_move:
            return self.get_state(), -1, True

        if self.game_over:
            if self.winner == 0:
                return self.get_state(), 0, True
            return self.get_state(), 1, True

        return self.get_state(), 0, False

    def switch_player(self):
        if self.current_player == self.PLAYER_1:
            self.current_player = self.PLAYER_2
        else:
            self.current_player = self.PLAYER_1

    def is_draw(self):
        return (
            len(self.get_valid_moves()) == 0
            and not self.check_win(self.PLAYER_1)
            and not self.check_win(self.PLAYER_2)
        )

    def check_win(self, player):
        # Horizontal check
        for row in range(self.ROWS):
            for col in range(self.COLS - 3):
                if all(self.board[row][col + i] == player for i in range(4)):
                    return True

        # Vertical check
        for row in range(self.ROWS - 3):
            for col in range(self.COLS):
                if all(self.board[row + i][col] == player for i in range(4)):
                    return True

        # Diagonal down-right check
        for row in range(self.ROWS - 3):
            for col in range(self.COLS - 3):
                if all(self.board[row + i][col + i] == player for i in range(4)):
                    return True

        # Diagonal up-right check
        for row in range(3, self.ROWS):
            for col in range(self.COLS - 3):
                if all(self.board[row - i][col + i] == player for i in range(4)):
                    return True

        return False

    def print_board(self):
        print(self.board)