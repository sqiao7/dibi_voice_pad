import numpy as np
import threading


class AudioBuffer:
    def __init__(self, capacity=48000 * 10):  # 10 seconds buffer at 48k
        self.capacity = capacity
        self.buffer = np.zeros((capacity, 2), dtype=np.float32)
        self.write_pos = 0
        self.read_pos = 0
        self.available = 0
        self.lock = threading.Lock()

    def write(self, data: np.ndarray):
        if data.size == 0:
            return

        frames = data.shape[0]
        if frames > self.capacity:
            # Too big to fit at all, just take the end
            data = data[-self.capacity :]
            frames = self.capacity

        with self.lock:
            # Simple circular buffer implementation:
            # If we write more than available space, we just overwrite and move read_pos?
            # NO. The standard way is:
            # write_pos moves forward.
            # If write_pos overtakes read_pos (overflow), read_pos must move forward to stay ahead.

            # 1. Calculate new end position
            new_write_pos = (self.write_pos + frames) % self.capacity

            # 2. Check if we are overwriting unread data
            # available space = capacity - available_count
            if frames > (self.capacity - self.available):
                # We are overflowing
                overflow = frames - (self.capacity - self.available)
                self.available = self.capacity  # Full
                # Move read_pos forward by overflow amount
                self.read_pos = (self.read_pos + overflow) % self.capacity
            else:
                self.available += frames

            # 3. Write data
            if new_write_pos > self.write_pos:
                # Contiguous
                self.buffer[self.write_pos : new_write_pos] = data
            else:
                # Wrap
                first_part = self.capacity - self.write_pos
                self.buffer[self.write_pos :] = data[:first_part]
                self.buffer[:new_write_pos] = data[first_part:]

            self.write_pos = new_write_pos

    def read(self, frames: int) -> np.ndarray:
        with self.lock:
            if self.available == 0:
                return np.zeros((frames, 2), dtype=np.float32)

            to_read = min(frames, self.available)

            end_pos = (self.read_pos + to_read) % self.capacity

            if end_pos > self.read_pos:
                result = self.buffer[self.read_pos : end_pos].copy()
            else:
                p1 = self.buffer[self.read_pos :]
                p2 = self.buffer[:end_pos]
                result = np.concatenate((p1, p2))

            self.read_pos = end_pos
            self.available -= to_read

            # Pad if not enough
            if result.shape[0] < frames:
                padding = np.zeros((frames - result.shape[0], 2), dtype=np.float32)
                result = np.vstack((result, padding))

            return result
