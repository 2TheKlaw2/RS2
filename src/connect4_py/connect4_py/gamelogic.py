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

    def get_winning_moves(self, player):
        winning_moves = []

        for col in self.get_valid_moves():
            row = self.get_next_open_row(col)

            if row is None:
                continue

            # Temporarily place a piece
            self.board[row][col] = player

            # Check if this move creates a win
            if self.check_win(player):
                winning_moves.append(col)

            # Undo the temporary move
            self.board[row][col] = self.EMPTY

        return winning_moves

    def get_windows_containing_cell(self, row, col):
        windows = []

        # Directions:
        # horizontal, vertical, diagonal down-right, diagonal up-right
        directions = [
            (0, 1),
            (1, 0),
            (1, 1),
            (-1, 1)
        ]

        for dr, dc in directions:
            for offset in range(-3, 1):
                window = []
                valid_window = True

                for i in range(4):
                    r = row + (offset + i) * dr
                    c = col + (offset + i) * dc

                    if r < 0 or r >= self.ROWS or c < 0 or c >= self.COLS:
                        valid_window = False
                        break

                    window.append(int(self.board[r][c]))

                if valid_window:
                    windows.append(window)

        return windows

    def score_hint_move(self, col, player):
        row = self.get_next_open_row(col)

        if row is None:
            return None

        opponent = self.PLAYER_2 if player == self.PLAYER_1 else self.PLAYER_1

        # Temporarily place the player's piece
        self.board[row][col] = player

        score = 0

        # Only score windows affected by this move
        windows = self.get_windows_containing_cell(row, col)

        for window in windows:
            player_count = window.count(player)
            opponent_count = window.count(opponent)
            empty_count = window.count(self.EMPTY)

            # Ignore lines already blocked by opponent pieces
            if opponent_count > 0:
                continue

            # Strongly reward moves that build toward 4 in a row
            if player_count == 4:
                score += 10000
            elif player_count == 3 and empty_count == 1:
                score += 500
            elif player_count == 2 and empty_count == 2:
                score += 100
            elif player_count == 1 and empty_count == 3:
                score += 10

        # Small centre preference only as a tie-breaker
        centre_col = self.COLS // 2
        distance_from_centre = abs(col - centre_col)
        score += (3 - distance_from_centre)

        # Penalise moves that allow the opponent to win immediately next turn
        opponent_winning_moves = self.get_winning_moves(opponent)

        if len(opponent_winning_moves) > 0:
            score -= 1000

        # Undo temporary move
        self.board[row][col] = self.EMPTY

        return score

    def get_best_hint_move(self, player):
        valid_moves = self.get_valid_moves()

        if len(valid_moves) == 0:
            return None

        opponent = self.PLAYER_2 if player == self.PLAYER_1 else self.PLAYER_1

        # Priority 1: if the human can win now, suggest that move
        winning_moves = self.get_winning_moves(player)

        if len(winning_moves) > 0:
            return winning_moves[0], "win"

        # Priority 2: if the opponent can win next turn, block it
        blocking_moves = self.get_winning_moves(opponent)

        if len(blocking_moves) > 0:
            return blocking_moves[0], "block"

        # Priority 3: suggest the best valid move to build toward 4 in a row
        best_score = -999999
        best_col = None

        for col in valid_moves:
            score = self.score_hint_move(col, player)

            if score is None:
                continue

            if score > best_score:
                best_score = score
                best_col = col

        if best_col is None:
            return None

        return best_col, "build"

    def print_board(self):
        print(self.board)