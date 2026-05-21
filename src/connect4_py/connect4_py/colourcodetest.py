import pyrealsense2 as rs
import numpy as np
import cv2


class UR3VisionSystem:
    def __init__(self):
        self.pipeline = rs.pipeline()
        self.config = rs.config()

        self.config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        self.config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)

        self.align = rs.align(rs.stream.color)

        # Yellow relaxed again so actual yellow pieces are detected
        self.yellow_low = np.array([12, 80, 90])
        self.yellow_high = np.array([42, 255, 255])

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

        # Smooth the grid so circles do not jump around frame-to-frame
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
            return 0, 0.0, 0.0, 0.0

        red_mask = cv2.bitwise_or(
            cv2.inRange(hsv_img, self.red_low1, self.red_high1),
            cv2.inRange(hsv_img, self.red_low2, self.red_high2)
        )

        yellow_mask = cv2.inRange(hsv_img, self.yellow_low, self.yellow_high)

        red_pixels = cv2.countNonZero(cv2.bitwise_and(red_mask, mask))
        yellow_pixels = cv2.countNonZero(cv2.bitwise_and(yellow_mask, mask))
        area = cv2.countNonZero(mask)

        if area == 0:
            return 0, 0.0, 0.0, 0.0

        red_ratio = red_pixels / area
        yellow_ratio = yellow_pixels / area

        depth = self.get_average_depth(depth_frame, x, y)

        if red_ratio > self.red_ratio_gate and red_ratio > yellow_ratio:
            return 1, depth, red_ratio, yellow_ratio

        if yellow_ratio > self.yellow_ratio_gate and yellow_ratio > red_ratio:
            return 2, depth, red_ratio, yellow_ratio

        return 0, depth, red_ratio, yellow_ratio

    def clean_board_state(self, board_state):
        cleaned = board_state.copy()

        for col in range(7):
            empty_seen_below = False

            for row in range(5, -1, -1):
                if cleaned[row][col] == 0:
                    empty_seen_below = True
                elif empty_seen_below:
                    cleaned[row][col] = 0

        return cleaned

    def run(self):
        print("Starting RealSense pipeline...")
        self.pipeline.start(self.config)
        print("Pipeline started.")

        try:
            while True:
                frames = self.pipeline.wait_for_frames()
                aligned_frames = self.align.process(frames)

                color_frame = aligned_frames.get_color_frame()
                depth_frame = aligned_frames.get_depth_frame()

                if not color_frame or not depth_frame:
                    continue

                color_img = np.asanyarray(color_frame.get_data())
                hsv = cv2.cvtColor(color_img, cv2.COLOR_BGR2HSV)
                gray = cv2.cvtColor(color_img, cv2.COLOR_BGR2GRAY)

                # Update grid slowly from Hough circles
                self.update_grid_from_hough(gray)

                board_state = np.zeros((6, 7), dtype=int)
                draw_data = []

                for row in range(6):
                    for col in range(7):
                        x = int(self.grid_x0 + col * self.grid_dx)
                        y = int(self.grid_y0 + row * self.grid_dy)

                        val, depth, red_ratio, yellow_ratio = self.get_slot_color(
                            hsv, depth_frame, x, y
                        )

                        board_state[row][col] = val
                        draw_data.append((row, col, x, y, val, depth, red_ratio, yellow_ratio))

                board_state = self.clean_board_state(board_state)

                for row, col, x, y, val, depth, red_ratio, yellow_ratio in draw_data:
                    val = board_state[row][col]

                    if val == 1:
                        color = (0, 0, 255)
                        label = "R"
                    elif val == 2:
                        color = (0, 255, 255)
                        label = "Y"
                    else:
                        color = (255, 255, 255)
                        label = "E"

                    cv2.circle(color_img, (x, y), self.slot_radius, color, 2)
                    cv2.putText(
                        color_img,
                        f"{row},{col}:{label}",
                        (x - 25, y + 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.4,
                        color,
                        1
                    )

                print("\n--- UPDATED BOARD STATE ---")
                print(board_state)

                cv2.imshow("Connect 4 Stable Grid", color_img)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        finally:
            self.pipeline.stop()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    UR3VisionSystem().run()