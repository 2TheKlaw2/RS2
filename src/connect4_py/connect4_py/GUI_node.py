import sys

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, String

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton,
    QLabel, QVBoxLayout, QHBoxLayout, QTextEdit, QComboBox
)
from PySide6.QtCore import QTimer

from connect4_py.visual import Connect4BoardWidget
from connect4_py.gamelogic import Connect4


class Connect4ROSNode(Node):
    def __init__(self, gui):
        super().__init__('connect4_node')
        self.gui = gui

        self.player_pub = self.create_publisher(Int32, 'player_move', 10)
        self.status_pub = self.create_publisher(String, 'game_status', 10)

        self.robot_sub = self.create_subscription(
            Int32,
            'robot_move',
            self.robot_move_callback,
            10
        )

        self.human_move_sub = self.create_subscription(
            Int32,
            'detected_human_move',
            self.human_move_callback,
            10
        )

        self.xr_move_sub = self.create_subscription(
            Int32,
            '/connect4/player_move',
            self.xr_move_callback,
            10
        )

        self.robot_status_sub = self.create_subscription(
            String,
            'robot_status',
            self.robot_status_callback,
            10
        )

        self.get_logger().info('Connect4 ROS 2 GUI node started')

    def publish_status(self, text: str):
        msg = String()
        msg.data = text
        self.status_pub.publish(msg)
        self.get_logger().info(f'Published status: {text}')

    def publish_player_move(self, column: int):
        msg = Int32()
        msg.data = column
        self.player_pub.publish(msg)
        self.get_logger().info(f'Published player move: {column}')

    def robot_move_callback(self, msg):
        self.gui.handle_robot_move(msg.data - 1)

    def human_move_callback(self, msg):
        self.gui.handle_human_move(msg.data - 1)

    def xr_move_callback(self, msg):
        self.gui.handle_xr_move(msg.data - 1)

    def robot_status_callback(self, msg):
        self.gui.handle_robot_status(msg.data)


class Connect4GUI(QWidget):
    def __init__(self):
        super().__init__()

        self.ros_node = None
        self.game_active = False
        self.current_turn = "None"
        self.selected_mode = "Easy"
        self.system_mode = "IRL"

        self.game = Connect4()
        self.board_widget = Connect4BoardWidget(self.game)

        self.setWindowTitle("Connect 4 Robot UI")
        self.resize(720, 950)

        self.start_button = QPushButton("Start Game")
        self.stop_button = QPushButton("Stop Game")
        self.estop_button = QPushButton("E-STOP")

        self.difficulty_box = QComboBox()
        self.difficulty_box.addItems(["Easy", "Hard"])

        self.system_mode_box = QComboBox()
        self.system_mode_box.addItems(["IRL", "XR"])

        self.robot_status = QLabel("Robot Status: IDLE")
        self.turn_label = QLabel("Turn: None")
        self.move_label = QLabel("Last Move: None")
        self.mode_label = QLabel("Mode: Easy")
        self.system_mode_label = QLabel("System Mode: IRL")

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        button_row = QHBoxLayout()
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.estop_button)

        difficulty_row = QHBoxLayout()
        difficulty_row.addWidget(QLabel("Game Mode:"))
        difficulty_row.addWidget(self.difficulty_box)

        system_mode_row = QHBoxLayout()
        system_mode_row.addWidget(QLabel("System Type:"))
        system_mode_row.addWidget(self.system_mode_box)

        layout = QVBoxLayout()
        layout.addLayout(button_row)
        layout.addLayout(difficulty_row)
        layout.addLayout(system_mode_row)
        layout.addWidget(self.mode_label)
        layout.addWidget(self.system_mode_label)
        layout.addWidget(self.robot_status)
        layout.addWidget(self.turn_label)
        layout.addWidget(self.move_label)
        layout.addWidget(self.board_widget)
        layout.addWidget(self.log)

        self.setLayout(layout)

        self.start_button.clicked.connect(self.start_game)
        self.stop_button.clicked.connect(self.stop_game)
        self.estop_button.clicked.connect(self.estop)
        self.difficulty_box.currentTextChanged.connect(self.set_difficulty)
        self.system_mode_box.currentTextChanged.connect(self.set_system_mode)

    def set_ros_node(self, ros_node):
        self.ros_node = ros_node

    def set_difficulty(self, difficulty):
        if self.game_active:
            self.log.append("Cannot change mode while game is active")
            self.difficulty_box.setCurrentText(self.selected_mode)
            return

        self.selected_mode = difficulty
        self.mode_label.setText(f"Mode: {difficulty}")
        self.log.append(f"Mode selected: {difficulty}")

        if self.ros_node is not None:
            self.ros_node.publish_status(f"MODE SELECTED: {difficulty}")

    def set_system_mode(self, mode):
        if self.game_active:
            self.log.append("Cannot change system mode while game is active")
            self.system_mode_box.setCurrentText(self.system_mode)
            return

        self.system_mode = mode
        self.system_mode_label.setText(f"System Mode: {mode}")

        if mode == "IRL":
            self.log.append("IRL mode selected: human vs autonomous robot")
        elif mode == "XR":
            self.log.append("XR mode selected: human vs VR player")

        if self.ros_node is not None:
            self.ros_node.publish_status(f"SYSTEM MODE: {mode}")

    def start_game(self):
        self.game_active = True
        self.move_label.setText("Last Move: None")
        self.mode_label.setText(f"Mode: {self.selected_mode}")
        self.system_mode_label.setText(f"System Mode: {self.system_mode}")

        self.game.reset()
        self.board_widget.refresh()

        self.log.append(f"Game started in {self.selected_mode} mode")
        self.log.append(f"System mode: {self.system_mode}")

        if self.selected_mode == "Easy":
            self.current_turn = "Player"
            self.robot_status.setText("Robot Status: READY")
            self.turn_label.setText("Turn: Player")
            self.log.append("Easy mode: human player starts first")
            self.log.append("Waiting for perception to detect human move...")

            if self.ros_node is not None:
                self.ros_node.publish_status(f"GAME STARTED: EASY MODE, {self.system_mode} MODE")
                self.ros_node.publish_status("WAITING FOR HUMAN MOVE")

        elif self.selected_mode == "Hard":
            self.current_turn = "Robot"
            self.turn_label.setText("Turn: Robot")

            if self.system_mode == "IRL":
                self.robot_status.setText("Robot Status: PLANNING")
                self.log.append("Hard mode: autonomous robot starts first")
                self.log.append("Waiting for robot move output...")

                if self.ros_node is not None:
                    self.ros_node.publish_status("GAME STARTED: HARD MODE, IRL MODE")
                    self.ros_node.publish_status("ROBOT PLANNING")

            elif self.system_mode == "XR":
                self.robot_status.setText("Robot Status: WAITING FOR XR PLAYER")
                self.log.append("Hard mode: XR player starts first")
                self.log.append("Waiting for XR player move from Unity...")

                if self.ros_node is not None:
                    self.ros_node.publish_status("GAME STARTED: HARD MODE, XR MODE")
                    self.ros_node.publish_status("WAITING FOR XR PLAYER MOVE")

    def stop_game(self):
        self.game_active = False
        self.current_turn = "None"

        self.robot_status.setText("Robot Status: STOPPED")
        self.turn_label.setText("Turn: None")
        self.log.append("Game stopped")

        if self.ros_node is not None:
            self.ros_node.publish_status("GAME STOPPED")

    def estop(self):
        self.game_active = False
        self.current_turn = "None"

        self.robot_status.setText("Robot Status: EMERGENCY STOP")
        self.turn_label.setText("Turn: None")
        self.log.append("!!! E-STOP ACTIVATED !!!")

        if self.ros_node is not None:
            self.ros_node.publish_status("EMERGENCY STOP")

    def handle_human_move(self, column):
        if not self.game_active:
            self.log.append(f"Ignored human move in column {column + 1}: game is not active")
            return

        if self.current_turn != "Player":
            self.log.append(f"Ignored human move in column {column + 1}: not player's turn")
            return

        if column < 0 or column >= self.game.COLS:
            self.log.append(f"Ignored human move: column {column + 1} is outside 1-7")
            return

        move_success = self.game.drop_piece(column, self.game.PLAYER_1)

        if not move_success:
            self.log.append(f"Ignored human move: column {column + 1} is full or invalid")
            return

        self.move_label.setText(f"Last Move: Human → Column {column + 1}")
        self.log.append(f"Perception detected human piece in column {column + 1}")
        self.board_widget.refresh()

        if self.game.game_over:
            self.end_game()
            return

        self.current_turn = "Robot"
        self.turn_label.setText("Turn: Robot")

        if self.system_mode == "IRL":
            self.robot_status.setText("Robot Status: PLANNING")
            self.log.append("Robot AI is now planning its move")

            if self.ros_node is not None:
                self.ros_node.publish_player_move(column + 1)
                self.ros_node.publish_status(f"HUMAN MOVE DETECTED: COLUMN {column + 1}")
                self.ros_node.publish_status("ROBOT PLANNING")

        elif self.system_mode == "XR":
            self.robot_status.setText("Robot Status: WAITING FOR XR PLAYER")
            self.log.append("Waiting for XR player move from Unity")

            if self.ros_node is not None:
                self.ros_node.publish_player_move(column + 1)
                self.ros_node.publish_status(f"HUMAN MOVE DETECTED: COLUMN {column + 1}")
                self.ros_node.publish_status("WAITING FOR XR PLAYER MOVE")

    def handle_robot_move(self, column):
        if self.system_mode == "XR":
            self.log.append("Ignored autonomous robot move because XR mode is active")
            return

        if not self.game_active:
            self.log.append(f"Ignored robot move in column {column + 1}: game is not active")
            return

        if self.current_turn != "Robot":
            self.log.append(f"Ignored robot move in column {column + 1}: not robot's turn")
            return

        if column < 0 or column >= self.game.COLS:
            self.log.append(f"Ignored robot move: column {column + 1} is outside 1-7")
            return

        move_success = self.game.drop_piece(column, self.game.PLAYER_2)

        if not move_success:
            self.log.append(f"Ignored robot move: column {column + 1} is full or invalid")
            return

        self.move_label.setText(f"Last Move: Robot → Column {column + 1}")
        self.log.append(f"Robot placed coin in column {column + 1}")
        self.board_widget.refresh()

        if self.game.game_over:
            self.end_game()
            return

        self.robot_status.setText("Robot Status: READY")
        self.current_turn = "Player"
        self.turn_label.setText("Turn: Player")
        self.log.append("Turn returned to player")
        self.log.append("Waiting for perception to detect next human move...")

        if self.ros_node is not None:
            self.ros_node.publish_status(f"ROBOT MOVE COMPLETE: COLUMN {column + 1}")
            self.ros_node.publish_status("WAITING FOR HUMAN MOVE")

    def handle_xr_move(self, column):
        if self.system_mode != "XR":
            self.log.append("Ignored XR player move because IRL mode is active")
            return

        if not self.game_active:
            self.log.append(f"Ignored XR move in column {column + 1}: game is not active")
            return

        if self.current_turn != "Robot":
            self.log.append(f"Ignored XR move in column {column + 1}: not XR player's turn")
            return

        if column < 0 or column >= self.game.COLS:
            self.log.append(f"Ignored XR move: column {column + 1} is outside 1-7")
            return

        move_success = self.game.drop_piece(column, self.game.PLAYER_2)

        if not move_success:
            self.log.append(f"Ignored XR move: column {column + 1} is full or invalid")
            return

        self.move_label.setText(f"Last Move: XR Player → Column {column + 1}")
        self.log.append(f"XR player dropped coin in column {column + 1}")
        self.board_widget.refresh()

        if self.game.game_over:
            self.end_game()
            return

        self.robot_status.setText("Robot Status: TELEOP READY")
        self.current_turn = "Player"
        self.turn_label.setText("Turn: Player")
        self.log.append("Turn returned to real human")
        self.log.append("Waiting for perception to detect next human move...")

        if self.ros_node is not None:
            self.ros_node.publish_status(f"XR MOVE COMPLETE: COLUMN {column + 1}")
            self.ros_node.publish_status("WAITING FOR HUMAN MOVE")

    def end_game(self):
        self.game_active = False
        self.current_turn = "None"
        self.turn_label.setText("Turn: None")
        self.robot_status.setText("Robot Status: GAME OVER")

        if self.game.winner == self.game.PLAYER_1:
            self.log.append("GAME OVER: Human player wins!")
            status = "GAME OVER: HUMAN WINS"

        elif self.game.winner == self.game.PLAYER_2:
            if self.system_mode == "IRL":
                self.log.append("GAME OVER: Robot wins!")
                status = "GAME OVER: ROBOT WINS"
            else:
                self.log.append("GAME OVER: XR player wins!")
                status = "GAME OVER: XR PLAYER WINS"

        else:
            self.log.append("GAME OVER: Draw!")
            status = "GAME OVER: DRAW"

        if self.ros_node is not None:
            self.ros_node.publish_status(status)

        self.board_widget.refresh()

    def handle_robot_status(self, status):
        if not self.game_active:
            self.log.append(f"Ignored robot status '{status}': game is not active")
            return

        self.robot_status.setText(f"Robot Status: {status}")
        self.log.append(f"Robot status update: {status}")

        if self.ros_node is not None:
            self.ros_node.publish_status(f"ROBOT STATUS: {status}")


def main(args=None):
    rclpy.init(args=args)

    app = QApplication(sys.argv)

    gui = Connect4GUI()
    ros_node = Connect4ROSNode(gui)
    gui.set_ros_node(ros_node)
    gui.show()

    ros_timer = QTimer()
    ros_timer.timeout.connect(lambda: rclpy.spin_once(ros_node, timeout_sec=0.0))
    ros_timer.start(50)

    exit_code = app.exec()

    ros_node.destroy_node()
    rclpy.shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()