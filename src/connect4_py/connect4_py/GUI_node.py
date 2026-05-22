import sys

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, String, Bool

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton,
    QLabel, QVBoxLayout, QHBoxLayout,
    QTextEdit, QComboBox, QFrame
)
from PySide6.QtCore import QTimer, Qt

from connect4_py.visual import Connect4BoardWidget
from connect4_py.gamelogic import Connect4


class Connect4ROSNode(Node):
    def __init__(self, gui):
        super().__init__('connect4_node')
        self.gui = gui

        # GUI / algorithm / XR publishers
        self.player_pub = self.create_publisher(Int32, '/connect4/player_move', 10)
        self.difficulty_pub = self.create_publisher(String, '/connect4/game_difficulty', 10)
        self.game_over_pub = self.create_publisher(Int32, '/connect4/game_over', 10)
        self.game_mode_pub = self.create_publisher(String, '/connect4/game_mode', 10)

        # Robot movement publishers
        self.arm_execute_pub = self.create_publisher(Int32, '/column_command', 10)
        self.game_start_pub = self.create_publisher(Bool, '/connect4/game_start', 10)
        self.estop_pub = self.create_publisher(Bool, '/connect4/estop', 10)
        self.stop_game_pub = self.create_publisher(Bool, '/connect4/stop_game', 10)

        # Move/status subscribers
        self.robot_sub = self.create_subscription(
            Int32,
            '/connect4/robot_move',
            self.robot_move_callback,
            10
        )

        self.human_move_sub = self.create_subscription(
            Int32,
            '/connect4/detected_human_move',
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
            '/connect4/robot_status',
            self.robot_status_callback,
            10
        )

        # VR / Unity sync subscribers
        self.board_state_sub = self.create_subscription(
            String,
            '/connect4/board_state',
            self.board_state_callback,
            10
        )

        self.reset_sub = self.create_subscription(
            Bool,
            '/connect4/reset',
            self.reset_callback,
            10
        )

        self.get_logger().info('Connect4 ROS 2 GUI node started')

    # Movement publish helpers

    def publish_game_start(self):
        msg = Bool()
        msg.data = True
        self.game_start_pub.publish(msg)
        self.get_logger().info('Published: game_start')

    def publish_estop(self):
        msg = Bool()
        msg.data = True
        self.estop_pub.publish(msg)
        self.get_logger().info('Published: E-STOP')

    def publish_stop_game(self):
        msg = Bool()
        msg.data = True
        self.stop_game_pub.publish(msg)
        self.get_logger().info('Published: stop_game')

    def publish_arm_execute(self, column: int):
        msg = Int32()
        msg.data = column
        self.arm_execute_pub.publish(msg)
        self.get_logger().info(f'Published arm execute: column {column}')

    # GUI / VR / algorithm publish helpers

    def publish_player_move(self, column: int):
        msg = Int32()
        msg.data = column
        self.player_pub.publish(msg)
        self.get_logger().info(f'Published player move: {column}')

    def publish_difficulty(self, difficulty: str):
        msg = String()
        msg.data = difficulty
        self.difficulty_pub.publish(msg)
        self.get_logger().info(f'Published difficulty: {difficulty}')

    def publish_game_mode(self, mode: str):
        msg = String()
        msg.data = mode
        self.game_mode_pub.publish(msg)
        self.get_logger().info(f'Published game mode: {mode}')

    def publish_game_over(self, winner: int):
        msg = Int32()
        msg.data = winner
        self.game_over_pub.publish(msg)
        self.get_logger().info(f'Published game over: winner={winner}')

    # Subscribers / callbacks

    def board_state_callback(self, msg):
        self.gui.check_board_sync(msg.data)

    def robot_move_callback(self, msg):
        self.gui.handle_robot_move(msg.data - 1)

    def human_move_callback(self, msg):
        self.gui.handle_human_move(msg.data - 1)

    def xr_move_callback(self, msg):
        self.gui.handle_xr_move(msg.data - 1)

    def robot_status_callback(self, msg):
        self.gui.handle_robot_status(msg.data)

    def reset_callback(self, msg):
        if msg.data:
            self.get_logger().info('VR reset received — restarting game')
            self.gui.start_game()


class Connect4GUI(QWidget):
    def __init__(self):
        super().__init__()

        self.ros_node = None
        self.game_active = False
        self.current_turn = "None"
        self.selected_mode = "Easy"
        self.system_mode = "IRL"

        self.human_score = 0
        self.opponent_score = 0

        self.game = Connect4()
        self.board_widget = Connect4BoardWidget(self.game)

        self.setWindowTitle("Connect 4 Robot UI")
        self.resize(1050, 760)

        self.title_label = QLabel("CONNECT 4 ROBOT CONTROL")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setObjectName("titleLabel")

        self.start_button = QPushButton("Start Game")
        self.stop_button = QPushButton("Stop Game")
        self.estop_button = QPushButton("E-STOP")
        self.hint_button = QPushButton("Show Hint")
        self.hint_button.setEnabled(False)

        self.start_button.setObjectName("yellowButton")
        self.stop_button.setObjectName("yellowButton")
        self.estop_button.setObjectName("redButton")
        self.hint_button.setObjectName("redButton")

        self.difficulty_box = QComboBox()
        self.difficulty_box.addItems(["Easy", "Hard"])

        self.system_mode_box = QComboBox()
        self.system_mode_box.addItems(["IRL", "XR"])

        self.robot_status = QLabel("Robot Status: IDLE")
        self.turn_label = QLabel("Turn: None")
        self.move_label = QLabel("Last Move: None")
        self.mode_label = QLabel("Mode: Easy")
        self.system_mode_label = QLabel("System Mode: IRL")
        self.score_label = QLabel("Score: Human 0 vs Robot 0")
        self.hint_label = QLabel("Hint: Start an Easy game to use hints")

        self.log_title = QLabel("Game Log")
        self.log_title.setAlignment(Qt.AlignCenter)
        self.log_title.setObjectName("sectionTitle")

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumWidth(360)

        button_row = QHBoxLayout()
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.estop_button)
        button_row.addWidget(self.hint_button)

        difficulty_row = QHBoxLayout()
        difficulty_row.addWidget(QLabel("Game Difficulty:"))
        difficulty_row.addWidget(self.difficulty_box)

        system_mode_row = QHBoxLayout()
        system_mode_row.addWidget(QLabel("System Type:"))
        system_mode_row.addWidget(self.system_mode_box)

        status_panel = QFrame()
        status_panel.setObjectName("statusPanel")

        status_layout = QVBoxLayout()
        status_layout.addLayout(button_row)
        status_layout.addLayout(difficulty_row)
        status_layout.addLayout(system_mode_row)

        status_layout.addWidget(self.mode_label)
        status_layout.addWidget(self.system_mode_label)
        status_layout.addWidget(self.score_label)
        status_layout.addWidget(self.hint_label)
        status_layout.addWidget(self.robot_status)
        status_layout.addWidget(self.turn_label)
        status_layout.addWidget(self.move_label)

        status_layout.addWidget(self.log_title)
        status_layout.addWidget(self.log)

        status_panel.setLayout(status_layout)

        body_row = QHBoxLayout()
        body_row.addWidget(self.board_widget)
        body_row.addWidget(status_panel)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.title_label)
        main_layout.addLayout(body_row)

        self.setLayout(main_layout)

        self.start_button.clicked.connect(self.start_game)
        self.stop_button.clicked.connect(self.stop_game)
        self.estop_button.clicked.connect(self.estop)
        self.hint_button.clicked.connect(self.show_hint)
        self.difficulty_box.currentTextChanged.connect(self.set_difficulty)
        self.system_mode_box.currentTextChanged.connect(self.set_system_mode)

        self.apply_styles()

    def apply_styles(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #003B8E;
                color: white;
                font-family: Arial;
                font-size: 14px;
            }

            QLabel {
                color: white;
                font-size: 14px;
                padding: 3px;
            }

            QLabel#titleLabel {
                font-size: 24px;
                font-weight: bold;
                color: #FFD600;
                padding: 12px;
                background-color: #002B66;
                border-radius: 10px;
            }

            QLabel#sectionTitle {
                font-size: 18px;
                font-weight: bold;
                color: #FFD600;
                padding-top: 10px;
            }

            QFrame#statusPanel {
                background-color: #002B66;
                border: 3px solid #FFD600;
                border-radius: 14px;
                padding: 12px;
            }

            QPushButton {
                font-weight: bold;
                border-radius: 8px;
                padding: 8px;
                min-height: 28px;
            }

            QPushButton#yellowButton {
                background-color: #FFD600;
                color: #111111;
                border: 2px solid #C9A900;
            }

            QPushButton#yellowButton:hover {
                background-color: #FFE75C;
            }

            QPushButton#redButton {
                background-color: #E53935;
                color: white;
                border: 2px solid #B71C1C;
            }

            QPushButton#redButton:hover {
                background-color: #FF5252;
            }

            QPushButton:disabled {
                background-color: #777777;
                color: #CCCCCC;
                border: 2px solid #555555;
            }

            QComboBox {
                background-color: white;
                color: #111111;
                padding: 6px;
                border-radius: 6px;
                min-height: 24px;
            }

            QTextEdit {
                background-color: #F7F7F7;
                color: #111111;
                border: 2px solid #FFD600;
                border-radius: 8px;
                padding: 6px;
                font-family: Consolas;
                font-size: 12px;
            }
        """)

    def set_ros_node(self, ros_node):
        self.ros_node = ros_node

    def check_board_sync(self, ai_board_str: str):
        gui_board_str = '\n'.join(
            ' '.join(str(cell) for cell in row)
            for row in self.game.board
        )

        if gui_board_str != ai_board_str:
            self.log.append('WARNING: GUI board out of sync with AI/VR node')

    def publish_difficulty(self):
        if self.ros_node is not None:
            self.ros_node.publish_difficulty(self.selected_mode)

    def get_opponent_name(self):
        if self.system_mode == "IRL":
            return "Robot"
        elif self.system_mode == "XR":
            return "XR Player"
        return "Opponent"

    def update_score_label(self):
        opponent_name = self.get_opponent_name()
        self.score_label.setText(
            f"Score: Human {self.human_score} vs {opponent_name} {self.opponent_score}"
        )

    def reset_score(self):
        self.human_score = 0
        self.opponent_score = 0
        self.update_score_label()

    def update_hint_button_state(self):
        can_use_hint = (
            self.game_active
            and self.selected_mode == "Easy"
            and self.current_turn == "Player"
        )

        self.hint_button.setEnabled(can_use_hint)

        if not self.game_active:
            self.hint_label.setText("Hint: Start an Easy game to use hints")
        elif self.selected_mode != "Easy":
            self.hint_label.setText("Hint: Disabled in Hard mode")
        elif self.current_turn != "Player":
            self.hint_label.setText("Hint: Available only on the human turn")
        else:
            self.hint_label.setText("Hint: Press Show Hint for help")

    def show_hint(self):
        if not self.game_active:
            self.hint_label.setText("Hint: Game is not active")
            return

        if self.selected_mode != "Easy":
            self.hint_label.setText("Hint: Disabled in Hard mode")
            return

        if self.current_turn != "Player":
            self.hint_label.setText("Hint: Only available on the human turn")
            return

        hint_result = self.game.get_best_hint_move(self.game.PLAYER_1)

        if hint_result is None:
            self.hint_label.setText("Hint: No valid moves available")
            return

        best_col, reason = hint_result
        display_col = best_col + 1

        if reason == "win":
            self.hint_label.setText(
                f"Hint: Play column {display_col} to win"
            )

        elif reason == "block":
            self.hint_label.setText(
                f"Hint: Play column {display_col} to block the opponent"
            )

        else:
            self.hint_label.setText(
                f"Hint: Play column {display_col} to build toward 4 in a row"
            )

    def set_difficulty(self, difficulty):
        if self.game_active:
            self.log.append("Cannot change difficulty while game is active")
            self.difficulty_box.setCurrentText(self.selected_mode)
            return

        self.selected_mode = difficulty
        self.mode_label.setText(f"Mode: {difficulty}")
        self.log.append(f"Difficulty selected: {difficulty}")

        self.publish_difficulty()
        self.update_hint_button_state()

    def set_system_mode(self, mode):
        if self.game_active:
            self.log.append("Cannot change system mode while game is active")
            self.system_mode_box.setCurrentText(self.system_mode)
            return

        self.system_mode = mode
        self.system_mode_label.setText(f"System Mode: {mode}")

        if self.ros_node is not None:
            self.ros_node.publish_game_mode(mode)

        self.reset_score()

        if mode == "IRL":
            self.log.append("IRL mode selected: human vs autonomous robot")
        elif mode == "XR":
            self.log.append("XR mode selected: human vs VR player")

        self.log.append("Score reset because system mode changed")
        self.update_hint_button_state()

    def start_game(self):
        self.game_active = True
        self.move_label.setText("Last Move: None")
        self.mode_label.setText(f"Mode: {self.selected_mode}")
        self.system_mode_label.setText(f"System Mode: {self.system_mode}")
        self.update_score_label()

        self.publish_difficulty()

        if self.ros_node is not None:
            self.ros_node.publish_game_mode(self.system_mode)
            self.ros_node.publish_game_start()

        self.game.reset()
        self.board_widget.refresh()

        self.log.append(f"Game started in {self.selected_mode} difficulty")
        self.log.append(f"System mode: {self.system_mode}")
        self.robot_status.setText("Robot Status: RUNNING")

        if self.selected_mode == "Easy":
            self.current_turn = "Player"
            self.turn_label.setText("Turn: Player")
            self.log.append("Easy difficulty: human player starts first")
            self.log.append("Waiting for perception to detect human move...")

        elif self.selected_mode == "Hard":
            self.current_turn = "Robot"
            self.turn_label.setText("Turn: Robot")

            if self.system_mode == "IRL":
                self.robot_status.setText("Robot Status: PLANNING")
                self.log.append("Hard difficulty: autonomous robot starts first")
                self.log.append("Waiting for robot move output...")

            elif self.system_mode == "XR":
                self.robot_status.setText("Robot Status: WAITING FOR XR PLAYER")
                self.log.append("Hard difficulty: XR player starts first")
                self.log.append("Waiting for XR player move from Unity...")

        self.update_hint_button_state()

    def stop_game(self):
        self.game_active = False
        self.current_turn = "None"

        self.robot_status.setText("Robot Status: STOPPING")
        self.turn_label.setText("Turn: None")
        self.log.append("Stop Game pressed — robot returning to reset position...")

        if self.ros_node is not None:
            self.ros_node.publish_stop_game()

        self.robot_status.setText("Robot Status: STOPPED")
        self.log.append("Score kept because system mode did not change")
        self.update_hint_button_state()

    def estop(self):
        self.game_active = False
        self.current_turn = "None"

        self.robot_status.setText("Robot Status: EMERGENCY STOP")
        self.turn_label.setText("Turn: None")
        self.log.append("!!! E-STOP ACTIVATED — robot halted immediately !!!")
        self.log.append("Press Stop Game to return robot to reset, then Start Game to resume.")

        if self.ros_node is not None:
            self.ros_node.publish_estop()

        self.update_hint_button_state()

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
        self.update_hint_button_state()

        if self.system_mode == "IRL":
            self.robot_status.setText("Robot Status: PLANNING")
            self.log.append("Robot AI is now planning its move")

            if self.ros_node is not None:
                self.ros_node.publish_difficulty(self.selected_mode)
                self.ros_node.publish_player_move(column + 1)

        elif self.system_mode == "XR":
            self.robot_status.setText("Robot Status: WAITING FOR XR PLAYER")
            self.log.append("Waiting for XR player move from Unity")

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

        self.update_hint_button_state()

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

        if self.ros_node is not None:
            self.ros_node.publish_arm_execute(column + 1)

        if self.game.game_over:
            self.end_game()
            return

        self.robot_status.setText("Robot Status: TELEOP READY")
        self.current_turn = "Player"
        self.turn_label.setText("Turn: Player")
        self.log.append("Turn returned to real human")
        self.log.append("Waiting for perception to detect next human move...")

        self.update_hint_button_state()

    def end_game(self):
        self.game_active = False
        self.current_turn = "None"
        self.turn_label.setText("Turn: None")
        self.robot_status.setText("Robot Status: GAME OVER")

        if self.game.winner == self.game.PLAYER_1:
            self.human_score += 1
            self.log.append("GAME OVER: Human player wins!")

        elif self.game.winner == self.game.PLAYER_2:
            self.opponent_score += 1

            if self.system_mode == "IRL":
                self.log.append("GAME OVER: Robot wins!")
            else:
                self.log.append("GAME OVER: XR player wins!")

        else:
            self.log.append("GAME OVER: Draw!")

        self.update_score_label()
        self.log.append(self.score_label.text())
        self.board_widget.refresh()
        self.update_hint_button_state()

        if self.ros_node is not None:
            self.ros_node.publish_game_over(self.game.winner)

    def handle_robot_status(self, status):
        if not self.game_active:
            self.log.append(f"Ignored robot status '{status}': game is not active")
            return

        self.robot_status.setText(f"Robot Status: {status}")
        self.log.append(f"Robot status update: {status}")


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