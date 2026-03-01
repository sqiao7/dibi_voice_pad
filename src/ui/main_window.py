import sys  # Add import sys
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QAction
from qfluentwidgets import FluentWindow, NavigationItemPosition, FluentIcon as FIF, SplashScreen
from PyQt6.QtGui import QIcon
import os

from .mixer_interface import MixerInterface
from .setting_interface import SettingInterface
from .music_interface import MusicInterface
from ..core.audio_engine import AudioEngine
from ..core.config_manager import ConfigManager
from ..utils.i18n import tr
from qfluentwidgets import InfoBar, InfoBarPosition


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.initWindow()
        self.initTray()

        # 音频引擎占位符
        self.audioEngine = None

        # 加载配置
        self.config = ConfigManager.load_config()

        # Set Language before UI init if present in config
        lang = self.config.get("language", "zh_CN")
        tr.set_language(lang)

        # 界面
        self.mixerInterface = MixerInterface(self)
        self.musicInterface = MusicInterface(self)
        self.settingInterface = SettingInterface(self)

        # 应用配置
        self.mixerInterface.loadConfig(self.config)
        self.settingInterface.loadConfig(self.config)

        # Init Music Monitor Button State
        self.musicInterface.setMonitorState(self.mixerInterface.musicChannel.monitorBtn.isChecked())

        # 添加子界面
        self.addSubInterface(self.mixerInterface, FIF.MUSIC, tr.t("mixer"))
        self.addSubInterface(self.musicInterface, FIF.ALBUM, tr.t("playlist"))

        # 添加开始混音按钮到导航栏 (Settings 之上)
        self.startMixingBtn = self.navigationInterface.addItem(routeKey="start_mixing", icon=FIF.PLAY, text=tr.t("start_mixing"), onClick=self.toggleMixingGlobal, position=NavigationItemPosition.BOTTOM)

        self.addSubInterface(self.settingInterface, FIF.SETTING, tr.t("settings"), NavigationItemPosition.BOTTOM)

        # 连接信号
        self.connectSignals()

        # Subscribe to language changes
        tr.add_listener(self.updateTexts)

    def updateTexts(self):
        self.setWindowTitle(tr.t("app_name"))
        self.trayIcon.setToolTip(tr.t("app_name"))
        self.showAction.setText(tr.t("show_main_window"))
        self.quitAction.setText(tr.t("exit"))

        # Update Navigation Items
        # FluentWindow navigation items update is tricky, usually need to access internal items
        # self.navigationInterface.items["mixer_interface"].setText(tr.t("mixer")) # Example if key matches
        # Let's try to update the widgets we know

        # It seems FluentWindow doesn't expose easy text update for nav items by object.
        # We might need to iterate or rely on widget objectName if used as key.
        # addSubInterface uses objectName as routeKey by default if not provided? No, it uses interface object.

        # Actually addSubInterface returns the item.
        # But we didn't store the return values for mixer/music/settings items.
        # We should probably store them or find a way to update.

        # For now, let's update what we can easily control.
        if self.startMixingBtn:
            # Check state
            if self.audioEngine and self.audioEngine.is_alive():
                self.startMixingBtn.setText(tr.t("stop_mixing"))
            else:
                self.startMixingBtn.setText(tr.t("start_mixing"))

    def toggleMixingGlobal(self):
        # 切换混音状态
        if self.audioEngine and self.audioEngine.is_alive():
            # 正在运行 -> 停止
            self.stopMixing()
        else:
            # 未运行 -> 启动
            # 获取 PID
            pid = self.mixerInterface.processCombo.currentData()

            # Let's debug print
            print(f"Toggle Mixing: PID={pid}")

            if pid is None:
                # Fallback: Check if there are items, maybe select first?
                if self.mixerInterface.processCombo.count() > 0:
                    self.mixerInterface.processCombo.setCurrentIndex(0)
                    pid = self.mixerInterface.processCombo.currentData()

            if pid is None:
                # Still None? Then we really can't capture process.
                print("No process selected, starting in Mic/Music only mode.")
                pid = 0  # Use 0 or None to indicate no process

            self.startMixing(pid)

    def initWindow(self):
        self.resize(1000, 700)
        # Handle icon path for PyInstaller (bundled in onefile)
        if getattr(sys, "frozen", False):
            # If frozen, use _MEIPASS
            base_path = sys._MEIPASS
            icon_path = os.path.join(base_path, "assets", "icon.ico")
        else:
            icon_path = os.path.join("assets", "icon.ico")

        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            # Fallback to local assets folder if bundled path fails (development mode behavior backup)
            self.setWindowIcon(QIcon("assets/icon.ico"))
        self.setWindowTitle(tr.t("app_name"))

    def autoStartMixing(self):
        # Disabled
        pass

    def initTray(self):
        self.trayIcon = QSystemTrayIcon(self)

        # Handle icon path for PyInstaller
        if getattr(sys, "frozen", False):
            base_path = sys._MEIPASS
            icon_path = os.path.join(base_path, "assets", "icon.ico")
        else:
            icon_path = os.path.join("assets", "icon.ico")

        if os.path.exists(icon_path):
            self.trayIcon.setIcon(QIcon(icon_path))
        else:
            # Fallback to local assets folder if bundled path fails
            self.trayIcon.setIcon(QIcon("assets/icon.ico"))

        self.trayIcon.setToolTip(tr.t("app_name"))

        # 托盘菜单
        self.trayMenu = QMenu()
        self.showAction = QAction(tr.t("show_main_window"), self)
        self.showAction.triggered.connect(self.showNormal)
        self.quitAction = QAction(tr.t("exit"), self)
        self.quitAction.triggered.connect(self.quitApp)

        self.trayMenu.addAction(self.showAction)
        self.trayMenu.addSeparator()
        self.trayMenu.addAction(self.quitAction)

        self.trayIcon.setContextMenu(self.trayMenu)
        self.trayIcon.activated.connect(self.onTrayIconActivated)
        self.trayIcon.show()

    def onTrayIconActivated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.activateWindow()

    def quitApp(self):
        self.saveAllConfig()
        self.is_quitting = True
        self.stopMixing()
        self.trayIcon.hide()
        QApplication.quit()

    def saveAllConfig(self):
        self.mixerInterface.saveConfig(self.config)
        self.settingInterface.saveConfig(self.config)
        ConfigManager.save_config(self.config)

    def connectSignals(self):
        # 混音器信号
        self.mixerInterface.startSignal.connect(self.startMixing)
        self.mixerInterface.stopSignal.connect(self.stopMixing)

        # 音量/静音信号需要更新正在运行的引擎
        self.mixerInterface.procVolumeSignal.connect(lambda _: self.updateEngineParams())
        self.mixerInterface.micVolumeSignal.connect(lambda _: self.updateEngineParams())
        self.mixerInterface.musicVolumeSignal.connect(lambda _: self.updateEngineParams())
        self.mixerInterface.procMuteSignal.connect(lambda _: self.updateEngineParams())
        self.mixerInterface.micMuteSignal.connect(lambda _: self.updateEngineParams())
        self.mixerInterface.musicMuteSignal.connect(lambda _: self.updateEngineParams())
        self.mixerInterface.procMonitorSignal.connect(lambda _: self.updateEngineParams())
        self.mixerInterface.micMonitorSignal.connect(lambda _: self.updateEngineParams())
        self.mixerInterface.musicMonitorSignal.connect(lambda _: self.updateEngineParams())

        # 麦克风设备变更
        self.mixerInterface.micDeviceChanged.connect(self.onMicDeviceChanged)
        # 进程变更
        self.mixerInterface.processChanged.connect(self.onProcessChanged)
        # 输出/监听设备变更
        self.settingInterface.deviceChanged.connect(self.onOutputDeviceChanged)

        # Music Monitor Button Sync
        self.musicInterface.monitorRequestSignal.connect(self.mixerInterface.musicChannel.setMonitor)
        self.mixerInterface.musicMonitorSignal.connect(self.musicInterface.setMonitorState)

    def onMicDeviceChanged(self, mic_id):
        if self.audioEngine and self.audioEngine.is_alive():
            print(f"Mic device changed to {mic_id}, updating engine...")
            self.audioEngine.set_mic_device(mic_id)

    def onProcessChanged(self, pid):
        if self.audioEngine and self.audioEngine.is_alive():
            print(f"Process changed to {pid}, updating engine...")
            self.audioEngine.set_process(pid)

    def onOutputDeviceChanged(self, mic_id_ignored, out_id, mon_id):
        # Update Music Interface Output (for native player)
        if out_id is not None:
            self.musicInterface.update_output_device(out_id)

        if self.audioEngine and self.audioEngine.is_alive():
            current_out = self.audioEngine.output_id
            if current_out != out_id:
                print(f"Output device changed to {out_id}, updating engine...")
                self.audioEngine.set_output_device(out_id)

            # Update monitor settings (ID or enabled state might have changed, handled by updateEngineParams usually,
            # but settingInterface only emits deviceChanged on ID change or explicit save?
            # Actually settingInterface emits deviceChanged when combo box changes.
            # So we should update monitor ID too.
            self.updateEngineParams()

    def updateEngineParams(self):
        if self.audioEngine and self.audioEngine.is_alive():
            # 从 UI 获取值
            proc_vol = self.mixerInterface.procChannel.slider.value() / 100.0
            mic_vol = self.mixerInterface.micChannel.slider.value() / 100.0
            music_vol = self.mixerInterface.musicChannel.slider.value() / 100.0
            mute_proc = self.mixerInterface.procChannel.muteBtn.isChecked()
            mute_mic = self.mixerInterface.micChannel.muteBtn.isChecked()
            mute_music = self.mixerInterface.musicChannel.muteBtn.isChecked()

            mon_proc = self.mixerInterface.procChannel.monitorBtn.isChecked()
            mon_mic = self.mixerInterface.micChannel.monitorBtn.isChecked()
            mon_music = self.mixerInterface.musicChannel.monitorBtn.isChecked()

            # 获取监听设备ID
            _, _, mon_id = self.settingInterface.get_selected_ids()

            self.audioEngine.update_volumes(proc_vol, mic_vol, mute_proc, mute_mic)
            self.audioEngine.set_music_volume(music_vol if not mute_music else 0)
            self.audioEngine.update_monitor(True, mon_id, mon_proc, mon_mic, mon_music)

    def startMixing(self, pid):
        # 1. 自动选择 CABLE Output 设备 (如果存在)
        if self.settingInterface.autoSelectCableOutput():
            print("Auto-selected CABLE Output device.")

        # 获取设备 ID
        # mic_id 从 MixerInterface 获取
        mic_id = self.mixerInterface.micCombo.currentData()
        # out_id, mon_id 从 SettingInterface 获取
        _, out_id, mon_id = self.settingInterface.get_selected_ids()

        if mic_id is None or out_id is None:
            print("请先选择设备。")
            return

        print(f"开始混音: PID={pid}, Mic={mic_id}, Out={out_id}, Mon={mon_id}")

        # 停止现有的（如果有）
        self.stopMixing()

        # 创建新引擎
        self.audioEngine = AudioEngine()
        self.audioEngine.configure(pid, mic_id, out_id, mon_id)

        # Manually set initial state BEFORE starting thread to ensure correct initial config
        proc_vol = self.mixerInterface.procChannel.slider.value() / 100.0
        mic_vol = self.mixerInterface.micChannel.slider.value() / 100.0
        music_vol = self.mixerInterface.musicChannel.slider.value() / 100.0
        mute_proc = self.mixerInterface.procChannel.muteBtn.isChecked()
        mute_mic = self.mixerInterface.micChannel.muteBtn.isChecked()
        mute_music = self.mixerInterface.musicChannel.muteBtn.isChecked()

        mon_proc = self.mixerInterface.procChannel.monitorBtn.isChecked()
        mon_mic = self.mixerInterface.micChannel.monitorBtn.isChecked()
        mon_music = self.mixerInterface.musicChannel.monitorBtn.isChecked()

        self.audioEngine.update_volumes(proc_vol, mic_vol, mute_proc, mute_mic)
        self.audioEngine.set_music_volume(music_vol if not mute_music else 0)
        self.audioEngine.update_monitor(True, mon_id, mon_proc, mon_mic, mon_music)

        # 连接信号
        self.audioEngine.levelSignal.connect(self.onEngineLevels)
        self.audioEngine.musicLevelSignal.connect(self.onMusicLevel)

        # 连接音乐结束信号
        self.audioEngine.musicFinishedSignal.connect(self.musicInterface._on_engine_finished)
        # 连接音乐进度信号
        self.audioEngine.musicProgressSignal.connect(self.musicInterface._on_engine_progress)
        # Connect music volume change (from engine to UI)
        self.audioEngine.musicVolumeChangedSignal.connect(self.onMusicVolumeChangedFromEngine)

        # 启动引擎
        self.audioEngine.start()

        # Switch Music Player to Engine Mode
        self.musicInterface.switch_to_engine_mode(self.audioEngine)

        # Update Navigation Button
        if self.startMixingBtn:
            self.startMixingBtn.setText(tr.t("stop_mixing"))
            self.startMixingBtn.setIcon(FIF.PAUSE)

        self.setWindowTitle(tr.t("app_name_mixing"))

        InfoBar.success(title=tr.t("started"), content=tr.t("engine_running"), orient=Qt.Orientation.Horizontal, isClosable=True, position=InfoBarPosition.TOP_RIGHT, duration=2000, parent=self)

    def onEngineLevels(self, proc, mic):
        self.mixerInterface.procChannel.setLevel(proc)
        self.mixerInterface.micChannel.setLevel(mic)

    def onMusicLevel(self, music):
        self.mixerInterface.musicChannel.setLevel(music)
        # Also update music interface bar
        self.musicInterface.update_music_level(music)

    def onMusicVolumeChangedFromEngine(self, volume):
        self.mixerInterface.setMusicVolume(volume)

    def stopMixing(self):
        if self.audioEngine:
            print("停止混音...")

            # Switch Music Player back to Native Mode
            self.musicInterface.switch_to_native_mode()

            # 停止引擎
            if self.audioEngine.is_alive():
                self.audioEngine.stop_engine()
                self.audioEngine.join()

            # 断开信号
            try:
                self.audioEngine.levelSignal.disconnect()
                self.audioEngine.musicLevelSignal.disconnect()
                self.audioEngine.musicVolumeChangedSignal.disconnect()
            except:
                pass

            self.audioEngine = None

        # Update UI State
        if self.startMixingBtn:
            self.startMixingBtn.setText(tr.t("start_mixing"))
            self.startMixingBtn.setIcon(FIF.PLAY)

        self.setWindowTitle(tr.t("app_name"))

    def closeEvent(self, event):
        behavior = self.settingInterface.get_close_behavior()

        # 保存配置 (无论最小化还是退出)
        self.saveAllConfig()

        if getattr(self, "is_quitting", False):
            self.stopMixing()
            event.accept()
            return

        if behavior == "minimize":
            event.ignore()
            self.hide()
            self.trayIcon.showMessage(tr.t("app_name"), tr.t("minimized_to_tray"), QSystemTrayIcon.MessageIcon.Information, 2000)
        else:
            # 退出程序
            self.stopMixing()
            self.trayIcon.hide()  # 隐藏托盘图标
            event.accept()
            QApplication.quit()  # 确保彻底退出
