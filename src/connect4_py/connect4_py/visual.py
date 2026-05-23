from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QFont
from PySide6.QtCore import Qt


class Connect4BoardWidget(QWidget):
    def __init__(self, game):
        super().__init__()
        self.game = game

        self.SQUARE_SIZE = 80
        self.RADIUS = self.SQUARE_SIZE // 2 - 8

        self.COLS = self.game.COLS
        self.ROWS = self.game.ROWS

        self.setFixedSize(
            self.COLS * self.SQUARE_SIZE,
            (self.ROWS + 1) * self.SQUARE_SIZE
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.fillRect(self.rect(), QColor(0, 0, 0))

        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 22))

        if not self.game.game_over:
            text = f"Player {self.game.current_player}'s turn"
        else:
            if self.game.winner == 0:
                text = "Draw!"
            else:
                text = f"Player {self.game.winner} wins!"

        painter.drawText(20, 45, text)

        for col in range(self.COLS):
            for row in range(self.ROWS):
                x = col * self.SQUARE_SIZE
                y = (row + 1) * self.SQUARE_SIZE

                painter.fillRect(
                    x, y,
                    self.SQUARE_SIZE,
                    self.SQUARE_SIZE,
                    QColor(0, 0, 255)
                )

                piece = self.game.board[row][col]

                if piece == self.game.PLAYER_1:
                    colour = QColor(0, 255, 0)
                elif piece == self.game.PLAYER_2:
                    colour = QColor(255, 0, 0)
                else:
                    colour = QColor(0, 0, 0)

                painter.setBrush(colour)
                painter.setPen(Qt.NoPen)

                painter.drawEllipse(
                    x + self.SQUARE_SIZE // 2 - self.RADIUS,
                    y + self.SQUARE_SIZE // 2 - self.RADIUS,
                    self.RADIUS * 2,
                    self.RADIUS * 2
                )

    def refresh(self):
        self.update()