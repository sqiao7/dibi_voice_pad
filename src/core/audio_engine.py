import sounddevice as sd
import numpy as np
import threading
import time
import soundfile as sf
import subprocess
import os
import tempfile
from proctap import ProcessAudioCapture
from .audio_utils import AudioBuffer
from PyQt6.QtCore import QObject, pyqtSignal
import traceback


class AudioEngine(QObject):
    levelSignal = pyqtSignal(float, float)  # proc_level, mic_level
    musicProgressSignal = pyqtSignal(int, int)  # position_ms, duration_ms
    musicLevelSignal = pyqtSignal(float)  # music_rms
    musicVolumeChangedSignal = pyqtSignal(float)  # music_volume changed (0.0-1.0)
    musicFinishedSignal = pyqtSignal()  # End of playback

    def __init__(self):
        super().__init__()
        self.process_buffer = AudioBuffer()
        self.mic_buffer = AudioBuffer()
        self.music_buffer = AudioBuffer()
        self.monitor_buffer = AudioBuffer()

        self.mic_stream = None
        self.output_stream = None
        self.monitor_stream = None
        self.process_capture = None

        self.target_pid = None
        self.mic_id = None
        self.output_id = None
        self.monitor_id = None

        self.process_vol = 1.0
        self.mic_vol = 1.0
        self.music_vol = 1.0
        self.mute_process = False
        self.mute_mic = False
        self.monitor_enabled = False
        self.monitor_process = False
        self.monitor_mic = False
        self.monitor_music = False
        self.resample_ratio = 1.0

        self._stop_event = threading.Event()
        self._thread = None
        self._running = False

        # Music Player State
        self.music_data = None
        self.music_samplerate = 48000
        self.music_pos = 0
        self.music_playing = False
        self.music_loop = False
        self.music_duration_ms = 0
        self.music_state = 0  # 0=Stopped, 1=Playing, 2=Paused

        # Internal State
        self.out_samplerate = 48000
        self.capture_rate = 48000
        self.captured_frames_count = 0
        self.capture_start_time = 0
        self.rate_detection_done = False
        self.detected_capture_rate = 48000

    def configure(self, pid, mic_id, out_id, monitor_id=None):
        self.target_pid = pid
        self.mic_id = mic_id
        self.output_id = out_id
        self.monitor_id = monitor_id

    def _extract_audio_from_video(self, file_path):
        """Extract audio from video file using ffmpeg to a temp wav file"""
        try:
            # Create a temp file path
            fd, temp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)

            # Run ffmpeg
            # ffmpeg -i input.mp4 -vn -acodec pcm_f32le -ar 48000 -ac 2 temp.wav -y
            cmd = ["ffmpeg", "-i", file_path, "-vn", "-acodec", "pcm_f32le", "-ar", "48000", "-ac", "2", temp_path, "-y"]  # No video  # Float 32 format  # 48kHz  # Stereo  # Overwrite

            # Hide console window on Windows
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)

            # Read the temp file
            data, rate = sf.read(temp_path, dtype="float32")

            # Clean up
            try:
                os.remove(temp_path)
            except:
                pass

            return data, rate
        except FileNotFoundError:
            print("FFmpeg not found. Please ensure ffmpeg is installed and in PATH.")
            return None, None
        except Exception as e:
            print(f"FFmpeg extraction failed: {e}")
            return None, None

    def load_music(self, file_path):
        """Load music file into memory"""
        try:
            print(f"Loading music: {file_path}")
            try:
                data, rate = sf.read(file_path, dtype="float32")
            except Exception as e:
                print(f"Direct load failed, trying ffmpeg: {e}")
                data, rate = self._extract_audio_from_video(file_path)

            if data is None:
                print(f"Failed to load music: {file_path}")
                self.music_data = None
                return False

            if data.ndim == 1:
                data = np.column_stack((data, data))
            elif data.ndim == 2 and data.shape[1] == 1:
                data = np.column_stack((data, data))

            # Resample to Output Rate if known, else 48000
            target_rate = self.out_samplerate if self.out_samplerate > 0 else 48000

            if rate != target_rate:
                print(f"Resampling music from {rate}Hz to {target_rate}Hz")
                duration = len(data) / rate
                new_len = int(duration * target_rate)
                x_old = np.linspace(0, len(data), len(data))
                x_new = np.linspace(0, len(data), new_len)
                new_data = np.zeros((new_len, data.shape[1]), dtype=np.float32)
                for ch in range(data.shape[1]):
                    new_data[:, ch] = np.interp(x_new, x_old, data[:, ch])
                data = new_data
                rate = target_rate

            self.music_data = data
            self.music_samplerate = rate
            self.music_pos = 0
            self.music_duration_ms = int(len(data) / rate * 1000)
            self.music_playing = False
            self.music_state = 0
            print(f"Music loaded: {len(data)} frames, {self.music_duration_ms}ms")
            return True
        except Exception as e:
            print(f"Failed to load music (Outer Exception): {e}")
            self.music_data = None
            return False

    def play_music(self):
        if self.music_data is not None:
            self.music_playing = True
            self.music_state = 1
            print("Music Playing Started")
        else:
            print("Music Play Failed: No Data")

    def pause_music(self):
        self.music_playing = False
        self.music_state = 2
        print("Music Paused")

    def stop_music(self):
        self.music_playing = False
        self.music_pos = 0
        self.music_state = 0
        self.musicProgressSignal.emit(0, self.music_duration_ms)
        print("Music Stopped")

    def seek_music(self, pos_ms):
        if self.music_data is not None:
            frame = int(pos_ms / 1000.0 * self.music_samplerate)
            if frame < 0:
                frame = 0
            if frame >= len(self.music_data):
                frame = len(self.music_data) - 1
            self.music_pos = frame

    def set_music_loop(self, loop):
        self.music_loop = loop

    def set_music_volume(self, vol):
        clamped = max(0.0, min(1.0, vol))
        if abs(self.music_vol - clamped) > 0.001:
            self.music_vol = clamped
            self.musicVolumeChangedSignal.emit(clamped)
            # print(f"Music Volume set to: {clamped}")

    def update_volumes(self, proc_vol, mic_vol, mute_proc, mute_mic):
        self.process_vol = proc_vol
        self.mic_vol = mic_vol
        self.mute_process = mute_proc
        self.mute_mic = mute_mic

    def update_monitor(self, enabled, monitor_id, mon_proc=False, mon_mic=False, mon_music=False):
        old_id = self.monitor_id
        # monitor_enabled is now a master switch derived from ANY channel being monitored
        # OR we can keep it as "Device is selected and system is ready".
        # But if the user toggles individual channels, we want to start/stop stream if needed?
        # Let's say: Stream runs if monitor_id is valid AND (mon_proc OR mon_mic OR mon_music)
        # However, to avoid frequent start/stop, maybe just run if monitor_id is valid?
        # But that wastes CPU.
        # Let's stick to: Stream runs if ANY monitoring is enabled.

        self.monitor_process = mon_proc
        self.monitor_mic = mon_mic
        self.monitor_music = mon_music

        # Determine if monitoring should be active
        should_be_enabled = (mon_proc or mon_mic or mon_music) and (monitor_id is not None)

        self.monitor_enabled = should_be_enabled
        self.monitor_id = monitor_id

        if not self._running:
            return

        if old_id != monitor_id:
            self._restart_monitor_stream()
        else:
            # If stream is closed but enabled, open it
            if self.monitor_stream:
                if should_be_enabled:
                    try:
                        if not self.monitor_stream.active:
                            self.monitor_stream.start()
                            print(f"Monitor stream restarted/activated on {self.monitor_id}")
                    except Exception as e:
                        print(f"Failed to activate existing monitor stream: {e}")
                        self._restart_monitor_stream()
                else:
                    # If should be disabled but running, stop it?
                    if self.monitor_stream.active:
                        self.monitor_stream.stop()
                        print("Monitor stream stopped (no channels selected).")
            else:
                if should_be_enabled:
                    self._restart_monitor_stream()

    def set_mic_device(self, mic_id):
        if self.mic_id == mic_id:
            return
        print(f"Switching Mic to {mic_id}")
        self.mic_id = mic_id
        if self._running:
            self._restart_mic_stream()

    def set_output_device(self, out_id):
        if self.output_id == out_id:
            return
        print(f"Switching Output to {out_id}")
        self.output_id = out_id
        if self._running:
            self._restart_output_stream()

    def set_process(self, pid):
        if self.target_pid == pid:
            return
        print(f"Switching Process to {pid}")
        self.target_pid = pid
        if self._running:
            self._restart_process_capture()

    def _restart_mic_stream(self):
        if self.mic_stream:
            try:
                self.mic_stream.stop()
                self.mic_stream.close()
            except:
                pass
            self.mic_stream = None

        if self.mic_id is not None:
            try:
                # Query device info
                mic_info = sd.query_devices(self.mic_id, "input")
                mic_channels = min(2, mic_info["max_input_channels"])
                if mic_channels < 1:
                    mic_channels = 1
            except:
                mic_channels = 2

            try:
                self.mic_stream = sd.InputStream(
                    device=self.mic_id,
                    channels=mic_channels,
                    samplerate=48000,
                    callback=self._mic_callback,
                    blocksize=0,
                    dtype="float32",
                    latency="low",
                )
                self.mic_stream.start()
            except Exception as e:
                print(f"Failed to restart mic stream: {e}")

    def _restart_output_stream(self):
        if self.output_stream:
            try:
                self.output_stream.stop()
                self.output_stream.close()
            except:
                pass
            self.output_stream = None

        if self.output_id is not None:
            try:
                out_info = sd.query_devices(self.output_id, "output")
                self.out_samplerate = int(out_info["default_samplerate"])
            except:
                self.out_samplerate = 48000
                print("Failed to query output rate, defaulting to 48000")

            # Update resample ratio
            self.resample_ratio = self.out_samplerate / self.capture_rate
            print(f"Resample Ratio updated: {self.resample_ratio:.4f}")

            try:
                self.output_stream = sd.OutputStream(
                    device=self.output_id,
                    channels=2,
                    samplerate=self.out_samplerate,
                    callback=self._out_callback,
                    blocksize=512,
                    dtype="float32",
                    latency="low",
                )
                self.output_stream.start()
            except Exception as e:
                print(f"Failed to restart output stream: {e}")

    def _restart_monitor_stream(self):
        if self.monitor_stream:
            try:
                self.monitor_stream.stop()
                self.monitor_stream.close()
            except:
                pass
            self.monitor_stream = None

        if self.monitor_id is not None:
            try:
                # Attempt to use the same samplerate as the main output
                # This prevents buffer over/underflow if output is 44.1k and monitor is 48k
                monitor_rate = self.out_samplerate if self.out_samplerate > 0 else 48000

                print(f"Starting Monitor Stream on {self.monitor_id} at {monitor_rate}Hz")

                self.monitor_stream = sd.OutputStream(
                    device=self.monitor_id,
                    channels=2,
                    samplerate=monitor_rate,
                    blocksize=0,
                    dtype="float32",
                    callback=self._monitor_stream_callback,
                )
                if self.monitor_enabled:
                    self.monitor_stream.start()
                    print(f"Monitor stream started.")
            except Exception as e:
                print(f"Failed to restart monitor stream at {monitor_rate}Hz: {e}")
                # Fallback to default 48000 if device doesn't support the rate
                try:
                    print("Retrying Monitor Stream at 48000Hz...")
                    self.monitor_stream = sd.OutputStream(
                        device=self.monitor_id,
                        channels=2,
                        samplerate=48000,
                        blocksize=0,
                        dtype="float32",
                        callback=self._monitor_stream_callback,
                    )
                    if self.monitor_enabled:
                        self.monitor_stream.start()
                except Exception as e2:
                    print(f"Failed to restart monitor stream (fallback): {e2}")
        else:
            print("Monitor ID is None, skipping monitor stream start.")

    def _restart_process_capture(self):
        if self.process_capture:
            try:
                if hasattr(self.process_capture, "stop"):
                    self.process_capture.stop()
            except:
                pass
            self.process_capture = None

        if self.target_pid:
            # Reset rate detection
            self.rate_detection_done = False
            self.captured_frames_count = 0
            self.capture_start_time = 0

            try:
                self.process_capture = ProcessAudioCapture(self.target_pid, on_data=self._proc_callback)
                self.process_capture.start()

                # Start rate detection thread/wait logic?
                # Since we are already in _run_loop (if calling from inside), we can just let callbacks handle it.
                # But if called from UI thread, we don't want to block.
                # The _proc_callback handles rate detection logic.

            except Exception as e:
                print(f"Failed to restart process capture: {e}")
        else:
            # If PID is None/0, we just stop capture.
            pass

    def _proc_callback(self, data, _ignored):
        try:
            if isinstance(data, bytes):
                data = np.frombuffer(data, dtype=np.float32)

            if data.ndim == 1:
                if data.size % 2 == 0:
                    data = data.reshape(-1, 2)
                else:
                    data = data.reshape(-1, 1)
                    data = np.column_stack((data, data))

            if hasattr(data, "dtype") and data.dtype != np.float32:
                data = data.astype(np.float32)

            if data.ndim == 2 and data.shape[1] == 1:
                data = np.column_stack((data, data))

            if data.ndim == 2 and data.shape[1] > 2:
                data = data[:, :2]

            # Rate detection logic
            if not self.rate_detection_done:
                frames = data.shape[0]
                self.captured_frames_count += frames
                if self.capture_start_time == 0:
                    self.capture_start_time = time.time()
                else:
                    elapsed = time.time() - self.capture_start_time
                    if elapsed >= 1.0:
                        rate = self.captured_frames_count / elapsed
                        print(f"Measured capture rate: {rate:.2f} Hz")
                        if abs(rate - 44100) < 2000:
                            self.detected_capture_rate = 44100
                        elif abs(rate - 48000) < 2000:
                            self.detected_capture_rate = 48000
                        else:
                            self.detected_capture_rate = int(rate)
                        print(f"Snapped capture rate: {self.detected_capture_rate} Hz")
                        self.capture_rate = self.detected_capture_rate

                        # Update resample ratio since capture rate changed
                        if self.out_samplerate:
                            self.resample_ratio = self.out_samplerate / self.capture_rate

                        self.rate_detection_done = True

            # Apply resampling
            if self.rate_detection_done and abs(self.resample_ratio - 1.0) > 0.001:
                frames = data.shape[0]
                new_frames = int(frames * self.resample_ratio)
                if new_frames > 0:
                    x_old = np.arange(frames)
                    x_new = np.linspace(0, frames - 1, new_frames)
                    new_data = np.zeros((new_frames, data.shape[1]), dtype=data.dtype)
                    for ch in range(data.shape[1]):
                        new_data[:, ch] = np.interp(x_new, x_old, data[:, ch])
                    data = new_data

            self.process_buffer.write(data)
        except Exception as e:
            # print(f"Process Callback Error: {e}")
            pass

    def _mic_callback(self, indata, frames, time, status):
        if status:
            print(f"Mic Status: {status}")

        # Handle Mono
        if indata.shape[1] == 1:
            stereo_data = np.repeat(indata, 2, axis=1)
            self.mic_buffer.write(stereo_data)
        else:
            self.mic_buffer.write(indata.copy())

    def _monitor_stream_callback(self, outdata, frames, time, status):
        if self.monitor_enabled:
            data = self.monitor_buffer.read(frames)
            # Ensure correct shape
            if data.shape[0] < frames:
                pad = np.zeros((frames - data.shape[0], 2), dtype=np.float32)
                data = np.vstack((data, pad))
            outdata[:] = data
        else:
            outdata.fill(0)
            self.monitor_buffer.read(frames)  # Flush buffer

    def _out_callback(self, outdata, frames, time, status):
        if status:
            print(f"Out Status: {status}")

        # Latency Watchdog
        max_latency_frames = int(self.out_samplerate * 0.15)
        target_latency_frames = int(self.out_samplerate * 0.05)

        if self.process_buffer.available > max_latency_frames:
            drop_amount = self.process_buffer.available - target_latency_frames
            self.process_buffer.read(drop_amount)

        mic_max_latency = int(self.out_samplerate * 0.1)
        mic_target_latency = int(self.out_samplerate * 0.02)

        if self.mic_buffer.available > mic_max_latency:
            drop_amount = self.mic_buffer.available - mic_target_latency
            self.mic_buffer.read(drop_amount)

        proc_chunk = self.process_buffer.read(frames)
        mic_chunk = self.mic_buffer.read(frames)

        if proc_chunk.shape[0] < frames:
            pad = np.zeros((frames - proc_chunk.shape[0], 2), dtype=np.float32)
            proc_chunk = np.vstack((proc_chunk, pad))

        if mic_chunk.shape[0] < frames:
            pad = np.zeros((frames - mic_chunk.shape[0], 2), dtype=np.float32)
            mic_chunk = np.vstack((mic_chunk, pad))

        # Music Mixing
        music_chunk = np.zeros((frames, 2), dtype=np.float32)
        if self.music_playing and self.music_data is not None:
            remaining = len(self.music_data) - self.music_pos
            if remaining > 0:
                to_read = min(frames, remaining)
                chunk = self.music_data[self.music_pos : self.music_pos + to_read]
                music_chunk[:to_read] = chunk
                self.music_pos += to_read

                if to_read < frames and self.music_loop:
                    self.music_pos = 0
                    rest = frames - to_read
                    chunk2 = self.music_data[0:rest]
                    music_chunk[to_read : to_read + len(chunk2)] = chunk2
                    self.music_pos += len(chunk2)
            else:
                if self.music_loop:
                    self.music_pos = 0
                else:
                    self.music_playing = False
                    self.musicFinishedSignal.emit()
                    print("Music Finished")

        # Apply Volumes
        proc_final = proc_chunk * (0 if self.mute_process else self.process_vol)
        mic_final = mic_chunk * (0 if self.mute_mic else self.mic_vol)
        music_final = music_chunk * self.music_vol

        # Calculate Levels
        proc_rms = np.sqrt(np.mean(proc_final**2)) if proc_final.size > 0 else 0.0
        mic_rms = np.sqrt(np.mean(mic_final**2)) if mic_final.size > 0 else 0.0
        music_rms = np.sqrt(np.mean(music_final**2)) if music_final.size > 0 else 0.0

        try:
            self.levelSignal.emit(float(proc_rms), float(mic_rms))
            self.musicLevelSignal.emit(float(music_rms))

            if self.music_playing:
                current_ms = int(self.music_pos / self.music_samplerate * 1000)
                if self.music_pos % (frames * 10) < frames:
                    self.musicProgressSignal.emit(current_ms, self.music_duration_ms)
        except:
            pass

        mixed = proc_final + mic_final + music_final
        np.clip(mixed, -1.0, 1.0, out=mixed)

        outdata[:] = mixed

        if self.monitor_enabled:
            # Mix specifically for monitor
            monitor_mix = np.zeros_like(mixed)
            if self.monitor_process:
                monitor_mix += proc_final
            if self.monitor_mic:
                monitor_mix += mic_final
            if self.monitor_music:
                monitor_mix += music_final

            np.clip(monitor_mix, -1.0, 1.0, out=monitor_mix)
            self.monitor_buffer.write(monitor_mix.copy())

    def start(self):
        if self._running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def join(self):
        if self._thread:
            self._thread.join()

    def is_alive(self):
        return self._thread and self._thread.is_alive()

    def _run_loop(self):
        self._running = True
        print(f"Starting Audio Engine: PID={self.target_pid}, Mic={self.mic_id}, Out={self.output_id}, Mon={self.monitor_id}")

        self.process_buffer = AudioBuffer()
        self.mic_buffer = AudioBuffer()
        self.music_buffer = AudioBuffer()
        self.monitor_buffer = AudioBuffer()

        try:
            # Initialize Capture Rate to Default
            self.capture_rate = 48000

            # Start Process Capture
            self._restart_process_capture()

            # Start Mic Stream
            self._restart_mic_stream()

            # Start Output Stream
            self._restart_output_stream()

            # Start Monitor Stream (Must be after output stream to get samplerate)
            self._restart_monitor_stream()

            # Loop
            while not self._stop_event.is_set():
                time.sleep(0.5)

        except Exception as e:
            print(f"AudioEngine Error: {e}")
            traceback.print_exc()
        finally:
            self._cleanup()

    def stop_engine(self):
        self._stop_event.set()

    def _cleanup(self):
        print("Stopping Audio Engine...")
        if self.process_capture:
            try:
                if hasattr(self.process_capture, "stop"):
                    self.process_capture.stop()
            except:
                pass

        for stream in [self.mic_stream, self.output_stream, self.monitor_stream]:
            if stream:
                try:
                    stream.stop()
                    stream.close()
                except:
                    pass

        self.process_capture = None
        self.mic_stream = None
        self.output_stream = None
        self.monitor_stream = None
        self._running = False
        print("Audio Engine Stopped.")
