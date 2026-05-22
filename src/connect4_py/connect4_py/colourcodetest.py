import pyrealsense2 as rs
import numpy as np
import cv2

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, String


class UR3VisionSystem(Node):
    EMPTY = 0
    HUMAN = 1       # Yellow piece
    ROBOT_XR = 2    # Red piece

    def __init__(self):
        super().__init__("connect4_perception_node")

        # ROS publishers
        self.human_move_pub = self.create_publisher(
            Int32,
            "/connect4/detected_human_move",
            10
        )

        self.board_state_pub = self.create_publisher(
            String,
            "/connect4/board_state",
            10
        )

        # RealSense setup
        self.pipeline = rs.pipeline()
        self.config = rs.config()

        self.config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        self.config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)

        self.align = rs.align(rs.stream.color)

        # Yellow = human
        self.yellow_low = np.array([12, 80, 90])
        self.yellow_high = np.array([42, 255, 255])

        # Red = robot/XR
        self.red_low1 = np.array([0, 120, 70])
        self.red_high1 = np.array([10, 255, 255])
        self.red_low2 = np.array([170, 120, 70])
        self.red_high2 = np.array([180, 255, 255])

        self.red_ratio_gate = 0.18
        self.yellow_ratio_gate = 0.30

        # Stable grid settings
        self.grid_ready = False
        self.grid_x0 = 80
        self.grid_y0 = 65
        self.grid_dx = 72
        self.grid_dy = 72
        self.slot_radius = 26
        self.sample_radius = 13

        # Board tracking
        self.last_confirmed_board = np.zeros((6, 7), dtype=int)
        self.candidate_board = None
        self.stable_count = 0
        self.stable_required = 5

        # Prevent repeated publishing of the same move
        self.last_published_move = None

        self.get_logger().info("Connect4 perception node initialised")

    def update_grid_from_hough(self, gray_img):
        blurred = cv2.GaussianBlur(gray_img, (7, 7), 1.5)

        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=45,
            param1=50,
            param2=28,
            minRadius=18,
            maxRadius=34
        )

        if circles is None:
            return

        circles = np.round(circles[0, :]).astype("int")

        valid = [
            c for c in circles
            if 50 < c[0] < 590 and 35 < c[1] < 455
        ]

        if len(valid) < 25:
            return

        xs = sorted([c[0] for c in valid])
        ys = sorted([c[1] for c in valid])

        min_x, max_x = xs[0], xs[-1]
        min_y, max_y = ys[0], ys[-1]

        new_x0 = min_x
        new_y0 = min_y
        new_dx = (max_x - min_x) / 6.0
        new_dy = (max_y - min_y) / 5.0

        alpha = 0.10

        if not self.grid_ready:
            self.grid_x0 = new_x0
            self.grid_y0 = new_y0
            self.grid_dx = new_dx
            self.grid_dy = new_dy
            self.grid_ready = True
        else:
            self.grid_x0 = (1 - alpha) * self.grid_x0 + alpha * new_x0
            self.grid_y0 = (1 - alpha) * self.grid_y0 + alpha * new_y0
            self.grid_dx = (1 - alpha) * self.grid_dx + alpha * new_dx
            self.grid_dy = (1 - alpha) * self.grid_dy + alpha * new_dy

    def get_average_depth(self, depth_frame, x, y, radius=4):
        depths = []

        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    px = int(x + dx)
                    py = int(y + dy)

                    if 0 <= px < 640 and 0 <= py < 480:
                        d = depth_frame.get_distance(px, py)
                        if d > 0:
                            depths.append(d)

        if len(depths) == 0:
            return 0.0

        return float(np.median(depths))

    def get_slot_color(self, hsv_img, depth_frame, x, y):
        mask = np.zeros(hsv_img.shape[:2], dtype=np.uint8)
        cv2.circle(mask, (x, y), self.sample_radius, 255, -1)

        mean_h, mean_s, mean_v, _ = cv2.mean(hsv_img, mask=mask)

        # Empty holes are usually darker or less saturated than real pieces
        if mean_v < 65:
            return self.EMPTY, 0.0, 0.0, 0.0

        red_mask = cv2.bitwise_or(
            cv2.inRange(hsv_img, self.red_low1, self.red_high1),
            cv2.inRange(hsv_img, self.red_low2, self.red_high2)
        )

        yellow_mask = cv2.inRange(hsv_img, self.yellow_low, self.yellow_high)

        red_pixels = cv2.countNonZero(cv2.bitwise_and(red_mask, mask))
        yellow_pixels = cv2.countNonZero(cv2.bitwise_and(yellow_mask, mask))
        area = cv2.countNonZero(mask)

        if area == 0:
            return self.EMPTY, 0.0, 0.0, 0.0

        red_ratio = red_pixels / area
        yellow_ratio = yellow_pixels / area

        depth = self.get_average_depth(depth_frame, x, y)

        # IMPORTANT:
        # Human pieces are yellow and are encoded as 1.
        # Robot/XR pieces are red and are encoded as 2.
        if yellow_ratio > self.yellow_ratio_gate and yellow_ratio > red_ratio:
            return self.HUMAN, depth, red_ratio, yellow_ratio

        if red_ratio > self.red_ratio_gate and red_ratio > yellow_ratio:
            return self.ROBOT_XR, depth, red_ratio, yellow_ratio

        return self.EMPTY, depth, red_ratio, yellow_ratio

    def clean_board_state(self, board_state):
        cleaned = board_state.copy()

        for col in range(7):
            empty_seen_below = False

            for row in range(5, -1, -1):
                if cleaned[row][col] == self.EMPTY:
                    empty_seen_below = True
                elif empty_seen_below:
                    # Remove floating pieces caused by false detections
                    cleaned[row][col] = self.EMPTY

        return cleaned

    def board_to_string(self, board):
        return "\n".join(
            " ".join(str(int(cell)) for cell in row)
            for row in board
        )

    def publish_board_state(self, board):
        msg = String()
        msg.data = self.board_to_string(board)
        self.board_state_pub.publish(msg)

    def boards_equal(self, board_a, board_b):
        if board_a is None or board_b is None:
            return False

        return np.array_equal(board_a, board_b)

    def update_stable_board(self, detected_board):
        if self.candidate_board is None:
            self.candidate_board = detected_board.copy()
            self.stable_count = 1
            return None

        if self.boards_equal(self.candidate_board, detected_board):
            self.stable_count += 1
        else:
            self.candidate_board = detected_board.copy()
            self.stable_count = 1

        if self.stable_count >= self.stable_required:
            return self.candidate_board.copy()

        return None

    def find_new_human_move(self, previous_board, current_board):
        changed_cells = []

        for row in range(6):
            for col in range(7):
                old_cell = int(previous_board[row][col])
                new_cell = int(current_board[row][col])

                if old_cell != new_cell:
                    changed_cells.append((row, col, old_cell, new_cell))

        # Only accept one changed cell.
        # This prevents false publishing if lighting/camera noise changes multiple slots.
        if len(changed_cells) != 1:
            return None

        row, col, old_cell, new_cell = changed_cells[0]

        # Human = yellow = 1
        # Publish only when a new human/yellow piece appears.
        if old_cell == self.EMPTY and new_cell == self.HUMAN:
            return col + 1  # Convert 0-6 index to ROS/GUI column 1-7

        return None

    def publish_human_move(self, column):
        msg = Int32()
        msg.data = int(column)
        self.human_move_pub.publish(msg)

        self.get_logger().info(
            f"Published detected human move: column {column}"
        )

    def process_board_update(self, detected_board):
        stable_board = self.update_stable_board(detected_board)

        if stable_board is None:
            return

        self.publish_board_state(stable_board)

        detected_move = self.find_new_human_move(
            self.last_confirmed_board,
            stable_board
        )

        if detected_move is not None:
            # Avoid repeated publication of the exact same board/move
            move_key = (
                detected_move,
                self.board_to_string(stable_board)
            )

            if move_key != self.last_published_move:
                self.publish_human_move(detected_move)
                self.last_published_move = move_key

        # Update confirmed board after stable detection
        self.last_confirmed_board = stable_board.copy()

    def draw_board_overlay(self, color_img, board_state, draw_data):
        for row, col, x, y, val, depth, red_ratio, yellow_ratio in draw_data:
            val = board_state[row][col]

            if val == self.HUMAN:
                color = (0, 255, 255)
                label = "H/Y"
            elif val == self.ROBOT_XR:
                color = (0, 0, 255)
                label = "R/R"
            else:
                color = (255, 255, 255)
                label = "E"

            cv2.circle(color_img, (x, y), self.slot_radius, color, 2)

            cv2.putText(
                color_img,
                f"{row},{col}:{label}",
                (x - 28, y + 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                color,
                1
            )

    def run(self):
        print("Starting RealSense pipeline...")
        self.pipeline.start(self.config)
        print("Pipeline started.")

        try:
            while rclpy.ok():
                # Let ROS process callbacks if needed
                rclpy.spin_once(self, timeout_sec=0.001)

                frames = self.pipeline.wait_for_frames()
                aligned_frames = self.align.process(frames)

                color_frame = aligned_frames.get_color_frame()
                depth_frame = aligned_frames.get_depth_frame()

                if not color_frame or not depth_frame:
                    continue

                color_img = np.asanyarray(color_frame.get_data())
                hsv = cv2.cvtColor(color_img, cv2.COLOR_BGR2HSV)
                gray = cv2.cvtColor(color_img, cv2.COLOR_BGR2GRAY)

                self.update_grid_from_hough(gray)

                board_state = np.zeros((6, 7), dtype=int)
                draw_data = []

                for row in range(6):
                    for col in range(7):
                        x = int(self.grid_x0 + col * self.grid_dx)
                        y = int(self.grid_y0 + row * self.grid_dy)

                        val, depth, red_ratio, yellow_ratio = self.get_slot_color(
                            hsv,
                            depth_frame,
                            x,
                            y
                        )

                        board_state[row][col] = val

                        draw_data.append(
                            (row, col, x, y, val, depth, red_ratio, yellow_ratio)
                        )

                board_state = self.clean_board_state(board_state)

                self.process_board_update(board_state)

                self.draw_board_overlay(color_img, board_state, draw_data)

                cv2.imshow("Connect 4 Perception", color_img)

                print("\n--- DETECTED BOARD STATE ---")
                print(board_state)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        finally:
            self.pipeline.stop()
            cv2.destroyAllWindows()


def main(args=None):
    rclpy.init(args=args)

    node = UR3VisionSystem()

    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()