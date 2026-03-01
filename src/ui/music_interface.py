from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QFileDialog, QLabel, QFrame, QSizePolicy, QMenu, QInputDialog, QMessageBox
from PyQt6.QtCore import Qt, QUrl, QTimer, QSize, QObject, pyqtSignal, QPoint
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from qfluentwidgets import SimpleCardWidget, BodyLabel, ProgressBar, ListWidget, PushButton, FluentIcon as FIF, CardWidget
from qfluentwidgets.multimedia import StandardMediaPlayBar
import os
import random
import shutil
import json


class EngineAudioOutput(QObject):
    volumeChanged = pyqtSignal(float)
    mutedChanged = pyqtSignal(bool)

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._volume = 1.0
        self._muted = False

        # Connect engine volume signal to update self
        self.engine.musicVolumeChangedSignal.connect(self._on_engine_volume_changed)

    def _on_engine_volume_changed(self, volume):
        if abs(self._volume - volume) > 0.001:
            self._volume = volume
            self.volumeChanged.emit(volume)

    def setVolume(self, volume):
        if abs(self._volume - volume) > 0.001:
            self._volume = volume
            # volume is 0.0 to 1.0
            self.engine.set_music_volume(volume if not self._muted else 0)
            self.volumeChanged.emit(volume)

    def volume(self):
        return self._volume

    def setMuted(self, muted):
        self._muted = muted
        self.engine.set_music_volume(self._volume if not muted else 0)
        self.mutedChanged.emit(muted)

    def isMuted(self):
        return self._muted

    def setDevice(self, device):
        pass  # Engine handles device internally


class EnginePlayer(QObject):
    positionChanged = pyqtSignal(int)
    durationChanged = pyqtSignal(int)
    playbackStateChanged = pyqtSignal(QMediaPlayer.PlaybackState)
    mediaStatusChanged = pyqtSignal(QMediaPlayer.MediaStatus)
    errorOccurred = pyqtSignal()
    volumeChanged = pyqtSignal(int)  # Changed to int for UI compatibility (0-100)
    mutedChanged = pyqtSignal(bool)

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._audioOutput = EngineAudioOutput(engine)

        # Connect internal output signal to public signal via converter
        self._audioOutput.volumeChanged.connect(self._on_audio_output_volume_changed)
        self._audioOutput.mutedChanged.connect(self.mutedChanged)

        # Connect engine signals
        self.engine.musicProgressSignal.connect(self._on_progress)
        self.engine.musicFinishedSignal.connect(self._on_finished)

    def _on_audio_output_volume_changed(self, volume_float):
        # Convert 0.0-1.0 to 0-100
        self.volumeChanged.emit(int(volume_float * 100))

    def audioOutput(self):
        return self._audioOutput

    def setAudioOutput(self, output):
        # Ignored, we use internal wrapper
        pass

    def volume(self):
        # Convert 0.0-1.0 to 0-100
        # If audioOutput is None, return 0
        if not self._audioOutput:
            return 0
        return int(self._audioOutput.volume() * 100)

    def setSource(self, source):
        # source is QUrl
        path = source.toLocalFile()
        if os.path.exists(path):
            if self.engine.load_music(path):
                self.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadedMedia)
                self.durationChanged.emit(self.engine.music_duration_ms)
                self.positionChanged.emit(0)
            else:
                self.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.NoMedia)
        else:
            self.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.NoMedia)

    def play(self):
        if self.engine.music_data is None:
            return

        self.engine.play_music()
        if self.engine.music_playing:
            self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.PlayingState)
        else:
            self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.StoppedState)

    def pause(self):
        self.engine.pause_music()
        self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.PausedState)

    def stop(self):
        self.engine.stop_music()
        self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.StoppedState)
        self.positionChanged.emit(0)

    def setPosition(self, pos):
        self.engine.seek_music(pos)
        self.positionChanged.emit(pos)

    def duration(self):
        return self.engine.music_duration_ms

    def position(self):
        return int(self.engine.music_pos / self.engine.music_samplerate * 1000) if self.engine.music_samplerate else 0

    def playbackState(self):
        if self.engine.music_playing:
            return QMediaPlayer.PlaybackState.PlayingState
        # Need to distinguish Paused vs Stopped?
        # AudioEngine state: 0=Stopped, 1=Playing, 2=Paused
        if self.engine.music_state == 2:
            return QMediaPlayer.PlaybackState.PausedState
        return QMediaPlayer.PlaybackState.StoppedState

    def mediaStatus(self):
        if self.engine.music_data is not None:
            return QMediaPlayer.MediaStatus.BufferedMedia
        return QMediaPlayer.MediaStatus.NoMedia

    def setVolume(self, volume):
        # Convert 0-100 to 0.0-1.0
        if self._audioOutput:
            self._audioOutput.setVolume(volume / 100.0)

    def setMuted(self, muted):
        if self._audioOutput:
            self._audioOutput.setMuted(muted)

    def isMuted(self):
        if self._audioOutput:
            return self._audioOutput.isMuted()
        return False

    def isPlaying(self):
        return self.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def _on_finished(self):
        self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.StoppedState)
        self.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.EndOfMedia)

    def _on_progress(self, pos, dur):
        self.positionChanged.emit(pos)
        self.durationChanged.emit(dur)


from ..utils.i18n import tr


class MusicInterface(QWidget):
    monitorRequestSignal = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MusicInterface")
        self.setAcceptDrops(True)

        # Main Layout
        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(30, 30, 30, 30)
        self.hBoxLayout.setSpacing(20)

        # --- Left Side: Playlist ---
        self.leftCard = SimpleCardWidget(self)
        self.leftLayout = QVBoxLayout(self.leftCard)
        self.leftLayout.setContentsMargins(0, 0, 0, 0)

        self.listTitle = BodyLabel(tr.t("playlist_title"), self.leftCard)
        self.listTitle.setStyleSheet("font-weight: bold; margin: 10px;")

        self.listWidget = ListWidget(self.leftCard)
        self.listWidget.setFrameShape(QFrame.Shape.NoFrame)
        self.listWidget.setAlternatingRowColors(True)
        self.listWidget.setStyleSheet("ListWidget { background-color: transparent; }")
        self.listWidget.itemDoubleClicked.connect(self.play_item)

        # Context Menu
        self.listWidget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.listWidget.customContextMenuRequested.connect(self.show_context_menu)

        self.addBtn = PushButton(FIF.ADD, tr.t("add_files"), self.leftCard)
        self.addBtn.clicked.connect(self.add_files)

        self.removeBtn = PushButton(FIF.DELETE, tr.t("remove_selected"), self.leftCard)
        self.removeBtn.clicked.connect(self.remove_current)

        self.listBtnsLayout = QHBoxLayout()
        self.listBtnsLayout.setContentsMargins(10, 10, 10, 10)
        self.listBtnsLayout.addWidget(self.addBtn)
        self.listBtnsLayout.addWidget(self.removeBtn)

        # Monitor Button
        self.monitorBtn = PushButton(FIF.HEADPHONE, tr.t("monitor"), self.leftCard)
        self.monitorBtn.setCheckable(True)
        self.monitorBtn.setToolTip(tr.t("monitor_global_tooltip"))
        self.monitorBtn.clicked.connect(self.on_monitor_btn_clicked)
        self.listBtnsLayout.addWidget(self.monitorBtn)

        self.leftLayout.addWidget(self.listTitle)
        self.leftLayout.addWidget(self.listWidget)
        self.leftLayout.addLayout(self.listBtnsLayout)

        # --- Right Side: Player ---
        self.rightCard = CardWidget(self)
        self.rightLayout = QVBoxLayout(self.rightCard)
        self.rightLayout.setSpacing(0)
        self.rightLayout.setContentsMargins(0, 0, 0, 0)

        # 1. Video Widget
        self.videoWidget = QVideoWidget(self.rightCard)
        self.videoWidget.setMinimumHeight(300)

        # 2. Audio Visualizer (ProgressBar)
        self.audioVisContainer = QWidget(self.rightCard)
        self.audioVisLayout = QVBoxLayout(self.audioVisContainer)
        self.audioVisLayout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.musicNoteIcon = QLabel(self.audioVisContainer)
        self.musicNoteIcon.setPixmap(FIF.MUSIC.icon().pixmap(128, 128))
        self.musicNoteIcon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.audioProgressBar = ProgressBar(self.audioVisContainer)
        self.audioProgressBar.setRange(0, 100)
        self.audioProgressBar.setValue(0)
        self.audioProgressBar.setFixedWidth(400)
        self.audioProgressBar.setFixedHeight(10)

        self.audioVisLayout.addWidget(self.musicNoteIcon)
        self.audioVisLayout.addSpacing(20)
        self.audioVisLayout.addWidget(self.audioProgressBar)

        # 3. Media Play Bar (Controls)
        self.playBar = StandardMediaPlayBar(self.rightCard)

        # Connect Native Player to Video Widget
        self.native_player = self.playBar.player
        self.native_player.setVideoOutput(self.videoWidget)

        # Ensure native player has audio output
        if not self.native_player.audioOutput():
            self.native_player.setAudioOutput(QAudioOutput())

        # Add to Right Layout
        self.rightLayout.addWidget(self.videoWidget, 1)
        self.rightLayout.addWidget(self.audioVisContainer, 1)
        self.rightLayout.addWidget(self.playBar, 0)

        # Add to Main Layout
        self.hBoxLayout.addWidget(self.leftCard, 1)
        self.hBoxLayout.addWidget(self.rightCard, 2)

        # Initialize State
        self.videoWidget.hide()
        self.audioVisContainer.show()

        self.playlist = []
        self.current_index = -1

        # Load playlist immediately (after widgets are ready)
        QTimer.singleShot(0, self.load_playlist)

        # Keep reference to original player (Native QMediaPlayer)
        self.native_player = self.playBar.player
        self.engine_player = None  # Created on demand
        self.current_player = self.native_player

        # Fake Audio Visualizer Timer (used when not in Engine mode)
        self.visTimer = QTimer(self)
        self.visTimer.setInterval(100)
        self.visTimer.timeout.connect(self.update_audio_visual)

        # Connect Signals
        self.connect_player_signals()

        self.current_output_id = None

        # Subscribe to language changes
        tr.add_listener(self.updateTexts)

    def updateTexts(self):
        self.listTitle.setText(tr.t("playlist_title"))
        self.addBtn.setText(tr.t("add_files"))
        self.removeBtn.setText(tr.t("remove_selected"))
        self.monitorBtn.setText(tr.t("monitor"))
        self.monitorBtn.setToolTip(tr.t("monitor_global_tooltip"))

    def connect_player_signals(self):
        self.current_player.mediaStatusChanged.connect(self.media_status_changed)
        self.current_player.playbackStateChanged.connect(self.playback_state_changed)
        self.current_player.errorOccurred.connect(self.handle_errors)

    def disconnect_player_signals(self):
        try:
            self.current_player.mediaStatusChanged.disconnect(self.media_status_changed)
            self.current_player.playbackStateChanged.disconnect(self.playback_state_changed)
            self.current_player.errorOccurred.disconnect(self.handle_errors)
        except:
            pass

    def switch_player(self, new_player):
        if self.current_player == new_player:
            return

        # Safety check: Ensure new_player has audioOutput before switching
        # This prevents crashes in PlayBar which assumes audioOutput exists
        if hasattr(new_player, "audioOutput") and hasattr(new_player, "setAudioOutput"):
            if not new_player.audioOutput():
                print("WARNING: Player missing audioOutput in switch_player. Creating one.")
                # Use self as parent to prevent GC
                new_player.setAudioOutput(QAudioOutput(self))

        self.disconnect_player_signals()
        self.current_player = new_player

        # StandardMediaPlayBar uses setMediaPlayer to change the player
        if hasattr(self.playBar, "setMediaPlayer"):
            self.playBar.setMediaPlayer(new_player)
        else:
            # Fallback for some versions? Or use internal property?
            pass

        self.connect_player_signals()

    def update_audio_visual(self):
        # Fake visualizer for Native mode
        if self.playBar.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            val = random.randint(30, 90)
            self.audioProgressBar.setValue(val)
        else:
            self.audioProgressBar.setValue(0)

    def update_music_level(self, level):
        # Real visualizer for Engine mode
        # level is RMS 0.0-1.0
        val = int(level * 300)  # Boost
        if val > 100:
            val = 100
        self.audioProgressBar.setValue(val)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        self.add_files_list(files)

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, tr.t("select_files_dialog"), "", "Media Files (*.mp3 *.wav *.flac *.m4a *.mp4 *.avi *.mkv *.webm);;All Files (*.*)")
        if files:
            self.add_files_list(files)

    def add_files_list(self, files):
        # Create 'files' directory if not exists
        target_dir = os.path.join(os.getcwd(), "files")
        if not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir)
            except OSError as e:
                print(f"Error creating directory {target_dir}: {e}")
                return

        for f in files:
            if os.path.isfile(f):
                filename = os.path.basename(f)
                target_path = os.path.join(target_dir, filename)

                # Copy file if it's not already in the target location
                abs_source = os.path.abspath(f)
                abs_target = os.path.abspath(target_path)

                if abs_source != abs_target:
                    try:
                        shutil.copy2(f, target_path)
                        print(f"Copied {f} to {target_path}")
                    except Exception as e:
                        print(f"Failed to copy {f}: {e}")
                        continue

                # Add to playlist if not present
                if abs_target not in self.playlist:
                    self.playlist.append(abs_target)
                    self.listWidget.addItem(filename)

    def show_context_menu(self, pos: QPoint):
        item = self.listWidget.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)

        play_action = menu.addAction(tr.t("play"))
        rename_action = menu.addAction(tr.t("rename"))
        remove_action = menu.addAction(tr.t("remove"))

        action = menu.exec(self.listWidget.mapToGlobal(pos))

        if action == play_action:
            self.play_item(item)
        elif action == rename_action:
            self.rename_item(item)
        elif action == remove_action:
            row = self.listWidget.row(item)
            self.remove_file_at_index(row)

    def rename_item(self, item):
        row = self.listWidget.row(item)
        old_path = self.playlist[row]
        old_name = os.path.basename(old_path)

        # Stop playback if this file is playing
        if row == self.current_index:
            self.stop_all()
            self.current_index = -1

        self.native_player.setSource(QUrl())
        # self.videoWidget.setVideo(QUrl()) # Removed QFW method

        new_name, ok = QInputDialog.getText(self, tr.t("rename"), tr.t("enter_new_name"), text=old_name)
        if ok and new_name and new_name != old_name:
            # Check extension
            _, ext = os.path.splitext(old_name)
            if not new_name.lower().endswith(ext.lower()):
                new_name += ext

            new_path = os.path.join(os.path.dirname(old_path), new_name)

            try:
                self.native_player.setSource(QUrl())
                os.rename(old_path, new_path)
                self.playlist[row] = new_path
                item.setText(new_name)
                print(f"Renamed {old_name} to {new_name}")
            except Exception as e:
                QMessageBox.warning(self, tr.t("error"), tr.t("rename_failed").format(e))

    def remove_file_at_index(self, row):
        if row < 0 or row >= len(self.playlist):
            return

        file_path = self.playlist[row]

        # Handle playback state BEFORE removing
        if row == self.current_index:
            self.stop_all()
            self.current_index = -1
        elif row < self.current_index:
            self.current_index -= 1

        # Release file locks
        self.native_player.setSource(QUrl())
        # self.videoWidget.setVideo(QUrl()) # Removed QFW method

        # Remove from UI
        self.listWidget.takeItem(row)
        del self.playlist[row]

        # Delete file from disk
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Deleted file: {file_path}")
        except Exception as e:
            print(f"Failed to delete file {file_path}: {e}")
            QMessageBox.warning(self, tr.t("error"), tr.t("delete_failed").format(e))

    def remove_current(self):
        row = self.listWidget.currentRow()
        self.remove_file_at_index(row)

    def load_playlist(self):
        target_dir = os.path.join(os.getcwd(), "files")

        if not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir)
            except OSError:
                return

        self.playlist = []
        try:
            files = os.listdir(target_dir)
            files.sort()

            for filename in files:
                full_path = os.path.join(target_dir, filename)
                if os.path.isfile(full_path):
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in [".mp3", ".wav", ".flac", ".m4a", ".mp4", ".avi", ".mkv", ".webm", ".mov"]:
                        self.playlist.append(os.path.abspath(full_path))
                        self.listWidget.addItem(filename)

            print(f"Loaded {len(self.playlist)} items from files directory.")
        except Exception as e:
            print(f"Failed to load files: {e}")

    def save_playlist(self):
        pass

    def play_item(self, item):
        row = self.listWidget.row(item)
        self.play_index(row)

    def reset_to_default(self):
        self.stop_all()

        # Ensure audio output
        if not self.native_player.audioOutput():
            self.native_player.setAudioOutput(QAudioOutput(self))
        else:
            self.native_player.audioOutput().setMuted(False)

        self.switch_player(self.native_player)
        self.engine_player = None

    def play_index(self, index):
        if 0 <= index < len(self.playlist):
            # Stop any current playback safely
            try:
                self.stop_all()
            except:
                pass

            self.current_index = index
            path = self.playlist[index]
            self.listWidget.setCurrentRow(index)

            filename = os.path.basename(path)
            ext = os.path.splitext(filename)[1].lower()
            is_video = ext in [".mp4", ".avi", ".mkv", ".webm", ".mov"]

            url = QUrl.fromLocalFile(path)

            # Check if Audio Engine is running
            engine_available = False
            engine = None
            if hasattr(self.window(), "audioEngine") and self.window().audioEngine and self.window().audioEngine.is_alive():
                engine = self.window().audioEngine
                engine_available = True

            should_use_engine = False
            if engine_available:
                # Try loading into engine first
                if engine.load_music(path):
                    should_use_engine = True
                else:
                    print("Engine failed to load file (maybe video format not supported by soundfile?), falling back to native.")

            if should_use_engine:
                print("Using AudioEngine for playback (Audio & Video)")
                # Create wrapper
                self.engine_player = EnginePlayer(engine)
                self.switch_player(self.engine_player)

                if is_video:
                    # Video Setup
                    self.audioVisContainer.hide()
                    self.playBar.show()  # We still need controls
                    self.videoWidget.show()

                    # We use a separate Native Player just for Video Display (Muted)
                    self.native_player.setSource(url)

                    # Mute video widget
                    # v_player = self._get_video_player() # Now we use self.native_player
                    v_player = self.native_player
                    if v_player:
                        # Ensure audio output exists and mute it
                        if not v_player.audioOutput():
                            v_player.setAudioOutput(QAudioOutput(self))

                        v_player.audioOutput().setMuted(True)

                        # Disconnect any old signals
                        try:
                            self.engine_player.playbackStateChanged.disconnect(self._sync_video_state)
                            self.engine_player.positionChanged.disconnect(self._sync_video_position)
                        except:
                            pass

                        # Connect sync signals
                        self.engine_player.playbackStateChanged.connect(self._sync_video_state)
                        self.engine_player.positionChanged.connect(self._sync_video_position)

                        # Initial state sync
                        self._sync_video_state(self.engine_player.playbackState())

                    self.engine_player.play()
                else:
                    # Audio Only Setup
                    self.videoWidget.hide()
                    try:
                        # v_player = self._get_video_player()
                        v_player = self.native_player
                        if v_player:
                            v_player.pause()
                    except:
                        pass
                    self.audioVisContainer.show()
                    self.playBar.show()
                    self.engine_player.play()

                self.visTimer.stop()

            else:
                # Native Mode (No Engine or Engine Load Failed)
                print("Using Native Player for playback")

                # Ensure audio output is set for native player BEFORE switching
                if not self.native_player.audioOutput():
                    self.native_player.setAudioOutput(QAudioOutput(self))
                    if self.current_output_id is not None:
                        self.update_output_device(self.current_output_id)
                else:
                    self.native_player.audioOutput().setMuted(False)

                self.switch_player(self.native_player)

                if is_video:
                    self.audioVisContainer.hide()
                    # If we hide playBar, how do we control it? Let's keep it shown.
                    self.playBar.show()

                    self.videoWidget.show()
                    # self.videoWidget.setVideo(url)
                    self.native_player.setSource(url)
                    self.native_player.play()
                else:
                    self.videoWidget.hide()
                    try:
                        # v_player = self._get_video_player()
                        v_player = self.native_player
                        if v_player:
                            v_player.pause()
                    except:
                        pass
                    self.audioVisContainer.show()
                    self.playBar.show()
                    self.native_player.setSource(url)
                    self.native_player.play()
                    self.visTimer.start()

    def _get_video_player(self):
        """Helper to get player, but now we use native_player directly."""
        return self.native_player

    def _sync_video_state(self, state):
        if self.videoWidget.isVisible():
            v_player = self.native_player
            if not v_player:
                return

            if state == QMediaPlayer.PlaybackState.PlayingState:
                v_player.play()
            elif state == QMediaPlayer.PlaybackState.PausedState:
                v_player.pause()
            elif state == QMediaPlayer.PlaybackState.StoppedState:
                v_player.pause()  # Stop resets to beginning usually

    def _sync_video_position(self, pos):
        # Sync every second or so? Or just let them run?
        # Continuous seeking is bad for performance.
        # Maybe only seek if drift is large?
        v_player = self.native_player

        if self.videoWidget.isVisible() and v_player and v_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            vid_pos = v_player.position()
            if abs(vid_pos - pos) > 500:  # 500ms drift
                v_player.setPosition(pos)

    def stop_all(self):
        self.visTimer.stop()
        self.audioProgressBar.setValue(0)

        # Stop whatever is playing
        if self.playBar.player:
            self.playBar.player.stop()

        try:
            self.videoWidget.pause()
        except:
            pass

    def media_status_changed(self, status):
        # Only for Audio Player (playBar)
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            # Auto next?
            pass
            # self.play_next()

    def playback_state_changed(self, state):
        if state != QMediaPlayer.PlaybackState.PlayingState:
            self.audioProgressBar.setValue(0)

    def play_next(self):
        if not self.playlist:
            return
        next_idx = self.current_index + 1
        if next_idx >= len(self.playlist):
            next_idx = 0  # Loop default?
        self.play_index(next_idx)

    def handle_errors(self):
        self.audioProgressBar.setValue(0)
        # print("Media Error")

    def on_monitor_btn_clicked(self, checked):
        # We need to update Mixer's switch
        # We can't access it easily without circular dependency or tight coupling.
        # So we'll emit a signal and let MainWindow handle it.
        self.monitorRequestSignal.emit(checked)

    def setMonitorState(self, checked):
        self.monitorBtn.setChecked(checked)

    def _on_engine_finished(self):
        # Called when ENGINE playback finishes
        # We trigger next song in playlist
        print("Engine playback finished, playing next...")
        pass
        # self.play_next()

    def _on_engine_progress(self, pos, dur):
        # We don't need to do much here, the EnginePlayer wrapper handles signals to PlayBar.
        pass

    def update_output_device(self, out_id):
        # We need to set output for BOTH players
        import sounddevice as sd
        from PyQt6.QtMultimedia import QMediaDevices

        try:
            device_info = sd.query_devices(out_id, "output")
            target_name = device_info["name"]

            devices = QMediaDevices.audioOutputs()
            best_match = None
            for dev in devices:
                if target_name in dev.description() or dev.description() in target_name:
                    best_match = dev
                    break

            if best_match:
                print(f"Setting Music Output to: {best_match.description()}")
                # Set for Audio Bar Player
                if self.playBar.player.audioOutput():
                    self.playBar.player.audioOutput().setDevice(best_match)
                else:
                    # Create if missing
                    ao = QAudioOutput(self)
                    ao.setDevice(best_match)
                    self.playBar.player.setAudioOutput(ao)

                # VideoWidget output device updated (handled by native_player above)

            else:
                self.playBar.player.audioOutput().setDevice(QMediaDevices.defaultAudioOutput())

        except Exception as e:
            print(f"Error setting music output: {e}")

    def switch_to_engine_mode(self, engine):
        if self.current_index < 0:
            return

        path = self.playlist[self.current_index]
        filename = os.path.basename(path)
        ext = os.path.splitext(filename)[1].lower()

        # Previously we skipped video files here. Now we want to try loading them.
        # if ext in [".mp4", ".avi", ".mkv", ".webm", ".mov"]:
        #    return  # Keep video as is

        was_playing = self.native_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        position = self.native_player.position()

        self.native_player.stop()
        self.visTimer.stop()

        if engine.load_music(path):
            self.engine_player = EnginePlayer(engine)
            self.switch_player(self.engine_player)

            # Handle Video Sync if it's a video file
            is_video = ext in [".mp4", ".avi", ".mkv", ".webm", ".mov"]
            if is_video:
                self.engine_player.playbackStateChanged.connect(self._sync_video_state)
                self.engine_player.positionChanged.connect(self._sync_video_position)
                self.videoWidget.show()
                # Mute video widget
                # v_player = self._get_video_player()
                v_player = self.native_player
                if v_player:
                    # Ensure audio output exists and mute it
                    if not v_player.audioOutput():
                        v_player.setAudioOutput(QAudioOutput(self))

                    v_player.audioOutput().setMuted(True)

                    # Restore position
                    v_player.setPosition(position)
            else:
                self.videoWidget.hide()

            if was_playing:
                engine.seek_music(position)
                self.engine_player.play()
        else:
            # Load failed, fallback
            self.native_player.setPosition(position)
            if was_playing:
                self.native_player.play()
            self.visTimer.start()

    def switch_to_native_mode(self):
        if self.current_index < 0:
            return

        if self.current_player == self.engine_player and self.engine_player:
            engine = self.engine_player.engine
            was_playing = engine.music_playing
            position = int(engine.music_pos / engine.music_samplerate * 1000) if engine.music_samplerate else 0

            # Disconnect sync signals
            try:
                self.engine_player.playbackStateChanged.disconnect(self._sync_video_state)
                self.engine_player.positionChanged.disconnect(self._sync_video_position)
            except:
                pass

            self.engine_player.stop()

            # Restore Audio Output for Native Player BEFORE switching
            # We need to set it back to default or current output
            v_player = self.native_player
            if v_player:
                # Re-create audio output if missing
                # Note: We pass 'self' as parent to ensure it persists
                if not v_player.audioOutput():
                    print("Restoring AudioOutput for Native Player...")
                    ao = QAudioOutput(self)
                    v_player.setAudioOutput(ao)

                    if self.current_output_id is not None:
                        self.update_output_device(self.current_output_id)
                else:
                    # Just unmute if it was muted
                    v_player.audioOutput().setMuted(False)
                    print("Native Player already has AudioOutput. Unmuting.")

            self.switch_player(self.native_player)
            self.engine_player = None

            path = self.playlist[self.current_index]
            url = QUrl.fromLocalFile(path)
            self.native_player.setSource(url)
            self.native_player.setPosition(position)

            if was_playing:
                self.native_player.play()

            self.visTimer.start()
