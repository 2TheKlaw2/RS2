import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton,
    QLabel, QVBoxLayout, QHBoxLayout,
    QTextEdit, QComboBox
)
from PySide6.QtCore import QTimer


class Connect4GUI(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Connect 4 Robot UI")
        self.resize(450, 350)

        # === Buttons ===
        self.start_button = QPushButton("Start Game")
        self.stop_button = QPushButton("Stop Game")
        self.estop_button = QPushButton("E-STOP")
        self.execute_button = QPushButton("Execute Robot Move")

        # === Difficulty ===
        self.difficulty_box = QComboBox()
        self.difficulty_box.addItems(["Easy", "Medium", "Hard"])

        # === Status ===
        self.robot_status = QLabel("Robot Status: IDLE")
        self.turn_label = QLabel("Turn: Player")
        self.move_label = QLabel("Last Move: None")

        # === Log ===
        self.log = QTextEdit()
        self.log.setReadOnly(True)

        # === Layout ===
        button_row = QHBoxLayout()
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.estop_button)

        action_row = QHBoxLayout()
        action_row.addWidget(self.execute_button)

        difficulty_row = QHBoxLayout()
        difficulty_row.addWidget(QLabel("Difficulty:"))
        difficulty_row.addWidget(self.difficulty_box)

        layout = QVBoxLayout()
        layout.addLayout(button_row)
        layout.addLayout(action_row)
        layout.addLayout(difficulty_row)
        layout.addWidget(self.robot_status)
        layout.addWidget(self.turn_label)
        layout.addWidget(self.move_label)
        layout.addWidget(self.log)

        self.setLayout(layout)

        # === Signals ===
        self.start_button.clicked.connect(self.start_game)
        self.stop_button.clicked.connect(self.stop_game)
        self.estop_button.clicked.connect(self.estop)
        self.execute_button.clicked.connect(self.execute_move)
        self.difficulty_box.currentTextChanged.connect(self.set_difficulty)

    # === GUI Actions ===
    def start_game(self):
        self.robot_status.setText("Robot Status: READY")
        self.turn_label.setText("Turn: Player")
        self.log.append("Game started")

    def stop_game(self):
        self.robot_status.setText("Robot Status: STOPPED")
        self.log.append("Game stopped")

    def estop(self):
        self.robot_status.setText("Robot Status: EMERGENCY STOP")
        self.log.append("!!! E-STOP ACTIVATED !!!")

    def set_difficulty(self, difficulty):
        self.log.append(f"Difficulty set to {difficulty}")

    # === Fake Robot Simulation ===
    def execute_move(self):
        self.turn_label.setText("Turn: Robot")
        self.robot_status.setText("Robot Status: PLANNING")
        self.log.append("Robot is planning move...")

        # Step 1: Planning → Moving
        QTimer.singleShot(1500, self.robot_moving)

    def robot_moving(self):
        self.robot_status.setText("Robot Status: MOVING")
        self.log.append("Robot is executing move...")

        # Step 2: Moving → Done
        QTimer.singleShot(2000, self.robot_done)

    def robot_done(self):
        column = 3  # fake column
        self.move_label.setText(f"Last Move: Robot → Column {column}")
        self.log.append(f"Robot placed coin in column {column}")

        self.robot_status.setText("Robot Status: READY")
        self.turn_label.setText("Turn: Player")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Connect4GUI()
    window.show()
    sys.exit(app.exec())