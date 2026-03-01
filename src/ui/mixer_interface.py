from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from qfluentwidgets import CardWidget, BodyLabel, TitleLabel, ComboBox, Slider, PushButton, SwitchButton, ToolButton, FluentIcon as FIF, ProgressBar, SimpleCardWidget, PrimaryPushButton, TransparentToolButton, StrongBodyLabel, CaptionLabel, TogglePushButton
from PyQt6.QtGui import QColor
from ..core.device_manager import DeviceManager
from ..utils.i18n import tr


class MixerChannel(SimpleCardWidget):
    """单独的混音通道控件"""

    volumeChanged = pyqtSignal(float)
    muteChanged = pyqtSignal(bool)
    monitorChanged = pyqtSignal(bool)

    def __init__(self, title, icon, parent=None, subtitle=""):
        super().__init__(parent=parent)
        self.setToolTip(subtitle)
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setSpacing(10)
        self.vBoxLayout.setContentsMargins(20, 15, 20, 15)

        # 标题栏 (包含图标、标题、监听按钮)
        self.titleLayout = QHBoxLayout()
        self.titleLayout.setContentsMargins(0, 0, 0, 0)
        self.titleLayout.setSpacing(15)  # Increase spacing between icon and text
        self.titleLayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # 图标
        self.iconLabel = ToolButton(icon, self)
        self.iconLabel.setFixedSize(32, 32)
        self.iconLabel.setEnabled(True)

        # 标题
        self.titleLabel = BodyLabel(title, self)
        self.titleLabel.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # 监听按钮
        self.monitorBtn = TogglePushButton(FIF.HEADPHONE, tr.t("monitor_on"), self)
        self.monitorBtn.setCheckable(True)
        self.monitorBtn.setFixedWidth(130)  # Ensure enough space for icon and text
        self.monitorBtn.setToolTip(tr.t("monitor_tooltip_off"))
        self.monitorBtn.setFixedHeight(32)

        self.titleLayout.addWidget(self.iconLabel)
        self.titleLayout.addWidget(self.titleLabel)
        self.titleLayout.addStretch(1)  # Push monitor button to the right
        self.titleLayout.addWidget(self.monitorBtn)

        self.vBoxLayout.addLayout(self.titleLayout)

        # 音量滑块布局
        self.volumeLayout = QHBoxLayout()
        self.volumeLayout.setSpacing(10)

        # 静音按钮放在左边，像播放器一样
        self.muteBtn = TransparentToolButton(FIF.VOLUME, self)
        self.muteBtn.setCheckable(True)
        self.muteBtn.setIconSize(QSize(20, 20))
        self.muteBtn.setToolTip(tr.t("mute_tooltip"))

        self.volumeLayout.addWidget(self.muteBtn)

        self.slider = Slider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(0, 100)
        self.volumeLayout.addWidget(self.slider)

        self.valueLabel = BodyLabel("100%", self)
        self.valueLabel.setFixedWidth(40)
        self.valueLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.volumeLayout.addWidget(self.valueLabel)

        self.vBoxLayout.addLayout(self.volumeLayout)

        # 电平条
        self.levelBar = ProgressBar(self)
        self.levelBar.setRange(0, 100)
        self.levelBar.setValue(0)
        self.levelBar.setFixedHeight(6)
        self.levelBar.setTextVisible(False)
        self.vBoxLayout.addWidget(self.levelBar)

        # 信号连接
        self.slider.valueChanged.connect(self.onSliderChanged)
        self.muteBtn.toggled.connect(self.onMuteToggled)
        self.monitorBtn.toggled.connect(self.onMonitorToggled)

        # Subscribe to language changes
        tr.add_listener(self.updateTexts)

    def updateTexts(self):
        # We need to handle title update from outside or store the key?
        # Since MixerChannel is instantiated with already translated text,
        # updating it requires knowing the original key.
        # But we passed "title" as string.
        # Refactoring MixerChannel to accept key or updating from MixerInterface is better.
        # However, for internal buttons like monitorBtn, we can update here.

        if self.monitorBtn.isChecked():
            self.monitorBtn.setText(tr.t("monitor_off"))
            self.monitorBtn.setToolTip(tr.t("monitor_tooltip_on"))
        else:
            self.monitorBtn.setText(tr.t("monitor_on"))
            self.monitorBtn.setToolTip(tr.t("monitor_tooltip_off"))

        if self.muteBtn.isChecked():
            self.muteBtn.setToolTip(tr.t("unmute_tooltip"))
        else:
            self.muteBtn.setToolTip(tr.t("mute_tooltip"))

    def setIcon(self, icon):
        self.iconLabel.setIcon(icon)

    def setTitle(self, title):
        self.titleLabel.setText(title)

    def onSliderChanged(self, value):
        self.valueLabel.setText(f"{value}%")
        self.volumeChanged.emit(value / 100.0)
        # Update icon based on volume if not muted
        if not self.muteBtn.isChecked():
            if value == 0:
                self.muteBtn.setIcon(FIF.MUTE)
            elif value < 30:
                self.muteBtn.setIcon(FIF.VOLUME)  # Low volume icon if available?
            else:
                self.muteBtn.setIcon(FIF.VOLUME)

    def onMuteToggled(self, checked):
        if checked:
            self.muteBtn.setIcon(FIF.MUTE)
            self.muteBtn.setToolTip(tr.t("unmute_tooltip"))
        else:
            self.muteBtn.setIcon(FIF.VOLUME)
            self.muteBtn.setToolTip(tr.t("mute_tooltip"))
        self.muteChanged.emit(checked)

    def onMonitorToggled(self, checked):
        if checked:
            self.monitorBtn.setToolTip(tr.t("monitor_tooltip_on"))
            self.monitorBtn.setText(tr.t("monitor_off"))
            self.monitorBtn.setIcon(FIF.CLOSE)
        else:
            self.monitorBtn.setToolTip(tr.t("monitor_tooltip_off"))
            self.monitorBtn.setText(tr.t("monitor_on"))
            self.monitorBtn.setIcon(FIF.HEADPHONE)

        self.monitorChanged.emit(checked)

    def setLevel(self, level):
        val = int(min(level * 100 * 2.5, 100))
        self.levelBar.setValue(val)
        # Force update if not visible?
        if not self.levelBar.isVisible():
            self.levelBar.show()

    def setVolume(self, volume):
        self.slider.setValue(volume)
        self.valueLabel.setText(f"{volume}%")

    def setMute(self, mute):
        self.muteBtn.setChecked(mute)
        self.onMuteToggled(mute)

    def setMonitor(self, monitor):
        self.monitorBtn.setChecked(monitor)
        self.onMonitorToggled(monitor)


class MixerInterface(QWidget):
    startSignal = pyqtSignal(int)  # pid
    stopSignal = pyqtSignal()
    procVolumeSignal = pyqtSignal(float)
    micVolumeSignal = pyqtSignal(float)
    musicVolumeSignal = pyqtSignal(float)  # New signal
    procMuteSignal = pyqtSignal(bool)
    micMuteSignal = pyqtSignal(bool)
    musicMuteSignal = pyqtSignal(bool)

    procMonitorSignal = pyqtSignal(bool)
    micMonitorSignal = pyqtSignal(bool)
    musicMonitorSignal = pyqtSignal(bool)

    micDeviceChanged = pyqtSignal(int)  # mic device id
    processChanged = pyqtSignal(int)  # pid

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("MixerInterface")

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(30, 30, 30, 30)
        self.vBoxLayout.setSpacing(20)

        # 标题
        self.titleLabel = TitleLabel(tr.t("mixer_console"), self)
        self.vBoxLayout.addWidget(self.titleLabel)

        # 顶部：进程选择 (Removed CardWidget, integrated into main layout)
        self.processLayout = QHBoxLayout()
        self.processLayout.setContentsMargins(10, 5, 10, 5)

        self.procIcon = ToolButton(FIF.GAME, self)
        self.procIcon.setEnabled(False)
        self.processCombo = ComboBox(self)
        self.processCombo.setPlaceholderText(tr.t("select_process"))
        self.refreshButton = ToolButton(FIF.SYNC, self)
        self.refreshButton.setToolTip(tr.t("refresh_process"))

        self.processLayout.addWidget(self.procIcon)
        self.processLayout.addWidget(self.processCombo, 1)
        self.processLayout.addWidget(self.refreshButton)

        self.vBoxLayout.addLayout(self.processLayout)

        # 麦克风选择 (Removed CardWidget, integrated into main layout)
        self.micSelectLayout = QHBoxLayout()
        self.micSelectLayout.setContentsMargins(10, 5, 10, 5)

        self.micSelectIcon = ToolButton(FIF.MICROPHONE, self)
        self.micSelectIcon.setEnabled(True)  # True for colored icon
        self.micCombo = ComboBox(self)
        self.micCombo.setPlaceholderText(tr.t("select_mic"))

        self.micRefreshButton = ToolButton(FIF.SYNC, self)
        self.micRefreshButton.setToolTip(tr.t("refresh_mic"))

        self.micSelectLayout.addWidget(self.micSelectIcon)
        self.micSelectLayout.addWidget(self.micCombo, 1)
        self.micSelectLayout.addWidget(self.micRefreshButton)

        self.vBoxLayout.addLayout(self.micSelectLayout)

        self.vBoxLayout.addSpacing(10)

        # 中部：混音通道 (并排布局)
        # Modified: Layout changed to VBox to stack channels vertically
        self.channelsLayout = QVBoxLayout()
        self.channelsLayout.setSpacing(20)

        # 进程通道
        self.procChannel = MixerChannel(tr.t("app_volume"), FIF.GAME, self, tr.t("app_volume_desc"))
        self.channelsLayout.addWidget(self.procChannel)

        # 麦克风通道
        self.micChannel = MixerChannel(tr.t("mic_volume"), FIF.MICROPHONE, self, tr.t("mic_volume_desc"))
        self.channelsLayout.addWidget(self.micChannel)

        # 音乐通道 (New)
        self.musicChannel = MixerChannel(tr.t("music_volume"), FIF.MUSIC, self, tr.t("music_volume_desc"))
        self.channelsLayout.addWidget(self.musicChannel)

        self.vBoxLayout.addLayout(self.channelsLayout)

        self.vBoxLayout.addStretch(1)

        # 信号连接
        self.refreshButton.clicked.connect(self.refreshProcesses)
        self.processCombo.currentIndexChanged.connect(self.onProcessChanged)

        self.micRefreshButton.clicked.connect(self.refreshMics)
        self.micCombo.currentIndexChanged.connect(self.onMicChanged)

        self.procChannel.volumeChanged.connect(self.procVolumeSignal.emit)
        self.procChannel.muteChanged.connect(self.procMuteSignal.emit)
        self.procChannel.monitorChanged.connect(self.procMonitorSignal.emit)

        self.micChannel.volumeChanged.connect(self.micVolumeSignal.emit)
        self.micChannel.muteChanged.connect(self.micMuteSignal.emit)
        self.micChannel.monitorChanged.connect(self.micMonitorSignal.emit)

        self.musicChannel.volumeChanged.connect(self.musicVolumeSignal.emit)
        self.musicChannel.muteChanged.connect(self.musicMuteSignal.emit)
        self.musicChannel.monitorChanged.connect(self.musicMonitorSignal.emit)

        # Subscribe to language changes
        tr.add_listener(self.updateTexts)

        # 初始化
        self.refreshProcesses()
        self.refreshMics()

    def updateTexts(self):
        self.titleLabel.setText(tr.t("mixer_console"))
        self.processCombo.setPlaceholderText(tr.t("select_process"))
        self.refreshButton.setToolTip(tr.t("refresh_process"))
        self.micCombo.setPlaceholderText(tr.t("select_mic"))
        self.micRefreshButton.setToolTip(tr.t("refresh_mic"))

        self.procChannel.setTitle(tr.t("app_volume"))
        self.procChannel.setToolTip(tr.t("app_volume_desc"))
        self.procChannel.updateTexts()

        self.micChannel.setTitle(tr.t("mic_volume"))
        self.micChannel.setToolTip(tr.t("mic_volume_desc"))
        self.micChannel.updateTexts()

        self.musicChannel.setTitle(tr.t("music_volume"))
        self.musicChannel.setToolTip(tr.t("music_volume_desc"))
        self.musicChannel.updateTexts()

    def refreshMics(self):
        self.micCombo.blockSignals(True)
        self.micCombo.clear()

        mics = DeviceManager.get_input_devices()
        default_index = 0
        saved_mic_name = getattr(self, "saved_mic_name", "")

        for i, m in enumerate(mics):
            name = m["name"]
            self.micCombo.addItem(f"{name} (ID: {m['id']})", userData=m["id"])

            if saved_mic_name and saved_mic_name in name:
                default_index = i

        if self.micCombo.count() > 0:
            self.micCombo.setCurrentIndex(default_index)

        self.micCombo.blockSignals(False)
        self.onMicChanged(self.micCombo.currentIndex())

    def loadConfig(self, config):
        self.saved_mic_name = config.get("mic_name", "")

        # Volumes
        self.procChannel.setVolume(int(config.get("proc_vol", 1.0) * 100))
        self.micChannel.setVolume(int(config.get("mic_vol", 1.0) * 100))
        self.musicChannel.setVolume(int(config.get("music_vol", 1.0) * 100))

        # Mute
        self.procChannel.setMute(config.get("proc_mute", False))
        self.micChannel.setMute(config.get("mic_mute", False))
        self.musicChannel.setMute(config.get("music_mute", False))

        # Monitor
        self.procChannel.setMonitor(config.get("proc_monitor", False))
        self.micChannel.setMonitor(config.get("mic_monitor", False))
        self.musicChannel.setMonitor(config.get("music_monitor", False))

        # Refresh mics to apply selection
        self.refreshMics()

    def saveConfig(self, config):
        config["mic_name"] = self.micCombo.currentText().split(" (ID:")[0] if self.micCombo.count() > 0 else ""
        config["proc_vol"] = self.procChannel.slider.value() / 100.0
        config["mic_vol"] = self.micChannel.slider.value() / 100.0
        config["music_vol"] = self.musicChannel.slider.value() / 100.0
        config["proc_mute"] = self.procChannel.muteBtn.isChecked()
        config["mic_mute"] = self.micChannel.muteBtn.isChecked()
        config["music_mute"] = self.musicChannel.muteBtn.isChecked()

        config["proc_monitor"] = self.procChannel.monitorBtn.isChecked()
        config["mic_monitor"] = self.micChannel.monitorBtn.isChecked()
        config["music_monitor"] = self.musicChannel.monitorBtn.isChecked()

    def onMicChanged(self, index):
        mic_id = self.micCombo.currentData()
        # No icon for mic currently, or we can use default mic icon
        self.micChannel.setIcon(FIF.MICROPHONE)
        if mic_id is not None:
            self.micDeviceChanged.emit(mic_id)

    def refreshProcesses(self):
        self.processCombo.clear()
        processes = DeviceManager.get_audio_processes()
        for p in processes:
            display_text = f"{p['title']} ({p['name']} - {p['pid']})"
            icon = DeviceManager.get_file_icon(p["exe"])

            # 修正：qfluentwidgets ComboBox.addItem 签名是 (text, userData=None, icon=None)
            self.processCombo.addItem(display_text, userData=p["pid"], icon=icon)

        # 确保初始选中项的图标被显示
        if self.processCombo.count() > 0:
            self.processCombo.setCurrentIndex(0)

    def onProcessChanged(self, index):
        # 当选中项改变时，更新左侧图标
        pid = 0
        if index >= 0 and index < self.processCombo.count():
            item_icon = self.processCombo.itemIcon(index)
            pid = self.processCombo.itemData(index)  # Get PID

            if item_icon and not item_icon.isNull():
                self.procIcon.setIcon(item_icon)
                self.procIcon.setEnabled(True)
                # Also update the channel icon
                self.procChannel.setIcon(item_icon)
            else:
                self.procIcon.setIcon(FIF.GAME)
                self.procIcon.setEnabled(True)
                self.procChannel.setIcon(FIF.GAME)
        else:
            self.procIcon.setIcon(FIF.GAME)
            self.procIcon.setEnabled(True)
            self.procChannel.setIcon(FIF.GAME)

        # Emit signal
        self.processChanged.emit(pid)

    # ... (in __init__)
    # self.processCombo.currentIndexChanged.connect(self.onProcessChanged)

    def onStartClicked(self, checked):
        # This function is now only called programmatically from MainWindow
        # or if we decide to keep a local button.
        # But since we removed the local button, this is just a helper/slot if needed.
        if checked:
            pid = self.processCombo.currentData()
            if pid:
                # self.startButton.setText("停止混音")
                # self.startButton.setIcon(FIF.PAUSE)
                self.startSignal.emit(pid)
            else:
                pass
                # self.startButton.setChecked(False)
        else:
            # self.startButton.setText("开始混音")
            # self.startButton.setIcon(FIF.PLAY)
            self.stopSignal.emit()

    def updateLevels(self, proc_level, mic_level, music_level=0.0):
        # Ensure level bars are visible and updated
        self.procChannel.setLevel(proc_level)
        self.micChannel.setLevel(mic_level)
        self.musicChannel.setLevel(music_level)

    def setMusicVolume(self, volume):
        # Update slider without emitting signal
        self.musicChannel.slider.blockSignals(True)
        self.musicChannel.setVolume(int(volume * 100))
        self.musicChannel.slider.blockSignals(False)
