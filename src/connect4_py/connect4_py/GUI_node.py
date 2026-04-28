import sys

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, String

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton,
    QLabel, QVBoxLayout, QHBoxLayout,
    QTextEdit, QComboBox
)
from PySide6.QtCore import QTimer


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

        self.get_logger().info('Connect4 ROS 2 node started')

    def send_player_move(self, column: int):
        # Publish the human player's selected column to ROS.
        msg = Int32()
        msg.data = column
        self.player_pub.publish(msg)

        status = String()
        status.data = f'PLAYER_MOVE_CONFIRMED: column {column}'
        self.status_pub.publish(status)

        self.get_logger().info(f'Published player move: {column}')

    def publish_status(self, text: str):
        # Helper to publish system status to ROS.
        msg = String()
        msg.data = text
        self.status_pub.publish(msg)
        self.get_logger().info(f'Published status: {text}')

    def robot_move_callback(self, msg):
        # Called when a robot move is received from another terminal/node.
        column = msg.data
        self.get_logger().info(f'Received robot move: {column}')
        self.gui.handle_robot_move(column)


class Connect4GUI(QWidget):
    def __init__(self):
        super().__init__()

        self.ros_node = None
        self.game_active = False
        self.waiting_for_robot_move = False
        self.player_move_confirmed = False
        self.current_turn = "None"

        self.setWindowTitle("Connect 4 Robot UI")
        self.resize(500, 420)

        # Main buttons
        self.start_button = QPushButton("Start Game")
        self.stop_button = QPushButton("Stop Game")
        self.estop_button = QPushButton("E-STOP")
        self.execute_button = QPushButton("Execute Robot Move")

        # Temporary manuanl move input for testing before future perception
        self.human_column_box = QComboBox()
        self.human_column_box.addItems([str(i) for i in range(7)])
        self.confirm_human_button = QPushButton("Confirm Human Move")

        # Difficulty selection
        self.difficulty_box = QComboBox()
        self.difficulty_box.addItems(["Easy", "Medium", "Hard"])

        # Status labels
        self.robot_status = QLabel("Robot Status: IDLE")
        self.turn_label = QLabel("Turn: None")
        self.move_label = QLabel("Last Move: None")

        # Event log
        self.log = QTextEdit()
        self.log.setReadOnly(True)

        # Layout rows
        button_row = QHBoxLayout()
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.estop_button)

        human_move_row = QHBoxLayout()
        human_move_row.addWidget(QLabel("Human Column:"))
        human_move_row.addWidget(self.human_column_box)
        human_move_row.addWidget(self.confirm_human_button)

        action_row = QHBoxLayout()
        action_row.addWidget(self.execute_button)

        difficulty_row = QHBoxLayout()
        difficulty_row.addWidget(QLabel("Difficulty:"))
        difficulty_row.addWidget(self.difficulty_box)

        layout = QVBoxLayout()
        layout.addLayout(button_row)
        layout.addLayout(human_move_row)
        layout.addLayout(action_row)
        layout.addLayout(difficulty_row)
        layout.addWidget(self.robot_status)
        layout.addWidget(self.turn_label)
        layout.addWidget(self.move_label)
        layout.addWidget(self.log)

        self.setLayout(layout)

        # Signals
        self.start_button.clicked.connect(self.start_game)
        self.stop_button.clicked.connect(self.stop_game)
        self.estop_button.clicked.connect(self.estop)
        self.execute_button.clicked.connect(self.execute_move)
        self.confirm_human_button.clicked.connect(self.confirm_human_move)
        self.difficulty_box.currentTextChanged.connect(self.set_difficulty)

        # Initial button states
        self.execute_button.setEnabled(False)
        self.confirm_human_button.setEnabled(False)
        self.human_column_box.setEnabled(False)

    def set_ros_node(self, ros_node):
        self.ros_node = ros_node

    def update_controls(self):
        # Whose logic
        if not self.game_active:
            self.confirm_human_button.setEnabled(False)
            self.human_column_box.setEnabled(False)
            self.execute_button.setEnabled(False)
            return

        if self.current_turn == "Player":
            self.confirm_human_button.setEnabled(True)
            self.human_column_box.setEnabled(True)
            self.execute_button.setEnabled(False)

        elif self.current_turn == "Robot":
            self.confirm_human_button.setEnabled(False)
            self.human_column_box.setEnabled(False)
            self.execute_button.setEnabled(not self.waiting_for_robot_move)
        else:
            self.confirm_human_button.setEnabled(False)
            self.human_column_box.setEnabled(False)
            self.execute_button.setEnabled(False)

    def start_game(self):
        # Start the game and set the first turn to the player
        self.game_active = True
        self.waiting_for_robot_move = False
        self.player_move_confirmed = False
        self.current_turn = "Player"

        self.robot_status.setText("Robot Status: READY")
        self.turn_label.setText("Turn: Player")
        self.move_label.setText("Last Move: None")
        self.log.append("Game started")
        self.log.append("Waiting for human move confirmation...")

        self.update_controls()

        if self.ros_node is not None:
            self.ros_node.publish_status("GAME STARTED")

    def stop_game(self):
        # Stop the game and prevent further actions.
        self.game_active = False
        self.waiting_for_robot_move = False
        self.player_move_confirmed = False
        self.current_turn = "None"

        self.robot_status.setText("Robot Status: STOPPED")
        self.turn_label.setText("Turn: None")
        self.log.append("Game stopped")

        self.update_controls()

        if self.ros_node is not None:
            self.ros_node.publish_status("GAME STOPPED")

    def estop(self):
        # Emergency stop.
        self.game_active = False
        self.waiting_for_robot_move = False
        self.player_move_confirmed = False
        self.current_turn = "None"

        self.robot_status.setText("Robot Status: EMERGENCY STOP")
        self.turn_label.setText("Turn: None")
        self.log.append("!!! E-STOP ACTIVATED !!!")

        self.update_controls()

        if self.ros_node is not None:
            self.ros_node.publish_status("EMERGENCY STOP")

    def set_difficulty(self, difficulty):
        self.log.append(f"Difficulty set to {difficulty}")

        if self.ros_node is not None:
            self.ros_node.publish_status(f"DIFFICULTY: {difficulty}")

    def confirm_human_move(self):
        # Temporary manual human move input.
        # Later, perception can replace this step automatically.
        if not self.game_active:
            self.log.append("Cannot confirm human move: game is not active")
            return

        if self.current_turn != "Player":
            self.log.append("Cannot confirm human move: it is not the player's turn")
            return

        column = int(self.human_column_box.currentText())
        self.player_move_confirmed = True

        self.move_label.setText(f"Last Move: Human → Column {column}")
        self.log.append(f"Human move confirmed in column {column}")

        if self.ros_node is not None:
            self.ros_node.send_player_move(column)
            self.ros_node.publish_status("HUMAN MOVE REGISTERED")

        # Turn passes to robot after human move is confirmed.
        self.current_turn = "Robot"
        self.turn_label.setText("Turn: Robot")
        self.robot_status.setText("Robot Status: WAITING TO EXECUTE")

        self.update_controls()

    def execute_move(self):
        # Trigger the robot turn and wait for a move from /robot_move.
        if not self.game_active:
            self.log.append("Cannot execute move: game is not active")
            return

        if self.current_turn != "Robot":
            self.log.append("Cannot execute robot move: it is not the robot's turn")
            return

        if self.waiting_for_robot_move:
            self.log.append("Already waiting for a robot move")
            return

        if not self.player_move_confirmed:
            self.log.append("Cannot execute robot move: no human move has been confirmed")
            return

        self.waiting_for_robot_move = True
        self.robot_status.setText("Robot Status: PLANNING")
        self.turn_label.setText("Turn: Robot")
        self.log.append("Robot move requested. Waiting for /robot_move...")

        self.update_controls()

        if self.ros_node is not None:
            self.ros_node.publish_status("ROBOT PLANNING")

    def handle_robot_move(self, column):
        # Accept robot move only when the GUI is expecting it.
        if not self.game_active:
            self.log.append(f"Ignored robot move {column}: game is not active")
            return

        if not self.waiting_for_robot_move:
            self.log.append(f"Ignored unexpected robot move {column}")
            return

        self.waiting_for_robot_move = False
        self.player_move_confirmed = False

        self.move_label.setText(f"Last Move: Robot → Column {column}")
        self.log.append(f"Robot placed coin in column {column}")

        self.robot_status.setText("Robot Status: READY")
        self.current_turn = "Player"
        self.turn_label.setText("Turn: Player")
        self.log.append("Turn returned to player")

        self.update_controls()

        if self.ros_node is not None:
            self.ros_node.publish_status(f"ROBOT READY AFTER COLUMN {column}")

def main(args=None):
    rclpy.init(args=args)

    app = QApplication(sys.argv)

    gui = Connect4GUI()
    ros_node = Connect4ROSNode(gui)
    gui.set_ros_node(ros_node)
    gui.show()

    # Keep ROS responsive without blocking the Qt GUI.
    ros_timer = QTimer()
    ros_timer.timeout.connect(lambda: rclpy.spin_once(ros_node, timeout_sec=0.0))
    ros_timer.start(50)

    exit_code = app.exec()

    ros_node.destroy_node()
    rclpy.shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()