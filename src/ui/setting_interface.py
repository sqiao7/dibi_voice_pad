from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from qfluentwidgets import ComboBox, BodyLabel, TitleLabel, CardWidget, PushButton, InfoBar, InfoBarPosition, FluentIcon as FIF
from ..core.device_manager import DeviceManager
from ..utils.i18n import tr
import os
import subprocess
import sys


class SettingInterface(QWidget):
    deviceChanged = pyqtSignal(int, int, object)  # mic_id, out_id, monitor_id (can be None)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("SettingInterface")

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(30, 30, 30, 30)
        self.vBoxLayout.setSpacing(20)

        # 标题
        self.titleLabel = TitleLabel(tr.t("settings_title"), self)
        self.vBoxLayout.addWidget(self.titleLabel)

        # 语言选择
        self.langCard = CardWidget(self)
        self.langLayout = QVBoxLayout(self.langCard)
        self.langLabel = BodyLabel(tr.t("interface_language"), self.langCard)
        self.langCombo = ComboBox(self.langCard)
        for code, name in tr.LANGUAGES.items():
            self.langCombo.addItem(name, userData=code)

        # Set current selection
        current_idx = 0
        for i in range(self.langCombo.count()):
            if self.langCombo.itemData(i) == tr.get_language():
                current_idx = i
                break
        self.langCombo.setCurrentIndex(current_idx)

        self.langLayout.addWidget(self.langLabel)
        self.langLayout.addWidget(self.langCombo)
        self.vBoxLayout.addWidget(self.langCard)

        # 输出选择
        self.outCard = CardWidget(self)
        self.outLayout = QVBoxLayout(self.outCard)
        self.outLabel = BodyLabel(tr.t("main_output"), self.outCard)
        self.outDesc = QLabel(tr.t("main_output_desc"), self.outCard)
        self.outDesc.setStyleSheet("color: #888888; font-size: 12px;")
        self.outDesc.setWordWrap(True)
        self.outCombo = ComboBox(self.outCard)

        self.outLayout.addWidget(self.outLabel)
        self.outLayout.addWidget(self.outDesc)
        self.outLayout.addWidget(self.outCombo)
        self.vBoxLayout.addWidget(self.outCard)

        # 监听设备选择
        self.monCard = CardWidget(self)
        self.monLayout = QVBoxLayout(self.monCard)
        self.monLabel = BodyLabel(tr.t("local_monitor"), self.monCard)
        self.monCombo = ComboBox(self.monCard)

        self.monLayout.addWidget(self.monLabel)
        self.monLayout.addWidget(self.monCombo)
        self.vBoxLayout.addWidget(self.monCard)

        # 关闭行为设置
        self.behaviorCard = CardWidget(self)
        self.behaviorLayout = QVBoxLayout(self.behaviorCard)
        self.behaviorLabel = BodyLabel(tr.t("close_behavior"), self.behaviorCard)
        self.behaviorCombo = ComboBox(self.behaviorCard)
        self.behaviorCombo.addItem(tr.t("minimize_tray"), userData="minimize")
        self.behaviorCombo.addItem(tr.t("exit_app"), userData="exit")

        self.behaviorLayout.addWidget(self.behaviorLabel)
        self.behaviorLayout.addWidget(self.behaviorCombo)
        self.vBoxLayout.addWidget(self.behaviorCard)

        # 高级设置 (打开日志/配置)
        self.advancedCard = CardWidget(self)
        self.advancedLayout = QHBoxLayout(self.advancedCard)
        self.advancedLabel = BodyLabel(tr.t("advanced"), self.advancedCard)

        self.openLogBtn = PushButton(tr.t("open_log"), self.advancedCard)
        self.openLogBtn.clicked.connect(self.openLogFolder)

        self.openConfigBtn = PushButton(tr.t("open_config"), self.advancedCard)
        self.openConfigBtn.clicked.connect(self.openConfigFile)

        self.advancedLayout.addWidget(self.advancedLabel)
        self.advancedLayout.addStretch(1)
        self.advancedLayout.addWidget(self.openLogBtn)
        self.advancedLayout.addWidget(self.openConfigBtn)

        self.vBoxLayout.addWidget(self.advancedCard)

        # 刷新按钮
        self.refreshBtn = PushButton(tr.t("refresh_devices"), self)
        self.refreshBtn.clicked.connect(self.refreshDevices)
        self.vBoxLayout.addWidget(self.refreshBtn, 0, Qt.AlignmentFlag.AlignRight)

        # 关于部分
        self.aboutCard = CardWidget(self)
        self.aboutLayout = QVBoxLayout(self.aboutCard)
        self.aboutLabel = BodyLabel(tr.t("about"), self.aboutCard)
        self.aboutDesc = QLabel(tr.t("about_desc"), self.aboutCard)
        self.aboutDesc.setStyleSheet("color: #888888; font-size: 12px;")
        self.aboutDesc.setWordWrap(True)

        self.aboutBtnsLayout = QHBoxLayout()
        self.websiteBtn = PushButton(tr.t("visit_website"), self.aboutCard)
        # Using a generic globe icon or similar for website if available, or just text
        self.websiteBtn.setIcon(FIF.GLOBE)
        self.websiteBtn.clicked.connect(lambda: self._open_url("https://github.com/sqiao7/DIBI_voice_pad"))  # Placeholder URL or real one

        self.githubBtn = PushButton(tr.t("visit_github"), self.aboutCard)
        self.githubBtn.setIcon(FIF.GITHUB)
        self.githubBtn.clicked.connect(lambda: self._open_url("https://github.com/sqiao7/DIBI_voice_pad"))

        self.aboutBtnsLayout.addWidget(self.websiteBtn)
        self.aboutBtnsLayout.addWidget(self.githubBtn)
        self.aboutBtnsLayout.addStretch(1)

        self.aboutLayout.addWidget(self.aboutLabel)
        self.aboutLayout.addWidget(self.aboutDesc)
        self.aboutLayout.addLayout(self.aboutBtnsLayout)

        self.vBoxLayout.addWidget(self.aboutCard)

        self.vBoxLayout.addStretch(1)

        # 连接信号
        self.langCombo.currentIndexChanged.connect(self.onLanguageChanged)
        self.outCombo.currentIndexChanged.connect(self.emitChange)
        self.monCombo.currentIndexChanged.connect(self.emitChange)
        self.behaviorCombo.currentIndexChanged.connect(self.onBehaviorChanged)

        # Subscribe to language changes
        tr.add_listener(self.updateTexts)

        self.refreshDevices()

    def updateTexts(self):
        self.titleLabel.setText(tr.t("settings_title"))
        self.langLabel.setText(tr.t("interface_language"))
        self.outLabel.setText(tr.t("main_output"))
        self.outDesc.setText(tr.t("main_output_desc"))
        self.monLabel.setText(tr.t("local_monitor"))
        self.behaviorLabel.setText(tr.t("close_behavior"))
        self.behaviorCombo.setItemText(0, tr.t("minimize_tray"))
        self.behaviorCombo.setItemText(1, tr.t("exit_app"))
        self.advancedLabel.setText(tr.t("advanced"))
        self.openLogBtn.setText(tr.t("open_log"))
        self.openConfigBtn.setText(tr.t("open_config"))
        self.refreshBtn.setText(tr.t("refresh_devices"))

        self.aboutLabel.setText(tr.t("about"))
        self.aboutDesc.setText(tr.t("about_desc"))
        self.websiteBtn.setText(tr.t("visit_website"))
        self.githubBtn.setText(tr.t("visit_github"))

    def onLanguageChanged(self, index):
        code = self.langCombo.itemData(index)
        if code and code != tr.get_language():
            tr.set_language(code)

    def onBehaviorChanged(self, index):
        # 可以在这里保存配置
        pass

    def openLogFolder(self):
        log_dir = os.path.abspath("logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        self._open_path(log_dir)

    def openConfigFile(self):
        config_file = os.path.abspath("config.json")
        if not os.path.exists(config_file):
            # Create empty if not exists
            with open(config_file, "w") as f:
                f.write("{}")
        self._open_path(config_file)

    def _open_path(self, path):
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.call(["open", path])
        else:
            subprocess.call(["xdg-open", path])

    def _open_url(self, url):
        import webbrowser

        webbrowser.open(url)

    def get_close_behavior(self):
        # 直接使用索引判断，这是最稳妥的方式
        # 0: 最小化到系统托盘
        # 1: 退出程序
        idx = self.behaviorCombo.currentIndex()
        if idx == 1:
            return "exit"
        return "minimize"

        # 检查是否安装了虚拟音频设备
        if not DeviceManager.check_virtual_audio_device_installed():
            self.showVirtualDeviceWarning()

    def showVirtualDeviceWarning(self):
        InfoBar.warning(
            title=tr.t("virtual_device_warning_title"),
            content=tr.t("virtual_device_warning"),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=-1,  # 不自动消失
            parent=self,
        )

        # 添加下载链接按钮（添加到输出卡片中）
        from qfluentwidgets import HyperlinkButton

        self.downloadLink = HyperlinkButton(url="https://vb-audio.com/Cable/", text=tr.t("download_driver"), parent=self.outCard)
        self.outLayout.addWidget(self.downloadLink)

    def refreshDevices(self):
        # ... (existing code) ...
        # self.micCombo.blockSignals(True)
        self.outCombo.blockSignals(True)
        self.monCombo.blockSignals(True)

        # self.micCombo.clear()
        self.outCombo.clear()
        self.monCombo.clear()

        outs = DeviceManager.get_output_devices()

        # 智能选择逻辑
        default_out_index = 0
        default_mon_index = 0

        # 优先使用保存的配置
        saved_out_name = getattr(self, "saved_out_name", "")
        saved_mon_name = getattr(self, "saved_mon_name", "")

        for i, o in enumerate(outs):
            name = o["name"]
            self.outCombo.addItem(f"{name} (ID: {o['id']})", userData=o["id"])
            self.monCombo.addItem(f"{name} (ID: {o['id']})", userData=o["id"])

            # 匹配保存的配置
            if saved_out_name and saved_out_name in name:
                default_out_index = i
            elif not saved_out_name:
                # 寻找最佳主输出 (虚拟线)
                name_lower = name.lower()
                if "cable" in name_lower or "virtual" in name_lower or "vb-audio" in name_lower:
                    default_out_index = i

            # 匹配保存的监听
            if saved_mon_name and saved_mon_name in name:
                default_mon_index = i
            elif not saved_mon_name:
                # 寻找最佳监听设备 (扬声器/耳机)
                name_lower = name.lower()
                if default_mon_index == 0:
                    if "speaker" in name_lower or "headphone" in name_lower or "扬声器" in name_lower or "耳机" in name_lower:
                        default_mon_index = i

        self.outCombo.blockSignals(False)
        self.monCombo.blockSignals(False)

        if self.outCombo.count() > 0:
            self.outCombo.setCurrentIndex(default_out_index)

        if self.monCombo.count() > 0:
            self.monCombo.setCurrentIndex(default_mon_index)

        self.emitChange()

    def loadConfig(self, config):
        self.saved_out_name = config.get("out_name", "")
        self.saved_mon_name = config.get("mon_name", "")

        behavior = config.get("close_behavior", "minimize")
        idx = 1 if behavior == "exit" else 0
        self.behaviorCombo.setCurrentIndex(idx)

        # Load language
        lang = config.get("language", "zh_CN")
        tr.set_language(lang)

        # Sync combo
        for i in range(self.langCombo.count()):
            if self.langCombo.itemData(i) == lang:
                self.langCombo.setCurrentIndex(i)
                break

        # 重新刷新以应用设备选择
        self.refreshDevices()

    def saveConfig(self, config):
        config["out_name"] = self.outCombo.currentText().split(" (ID:")[0] if self.outCombo.count() > 0 else ""
        config["mon_name"] = self.monCombo.currentText().split(" (ID:")[0] if self.monCombo.count() > 0 else ""
        config["close_behavior"] = self.get_close_behavior()
        config["language"] = tr.get_language()

    def emitChange(self):
        # mic_id = self.micCombo.currentData()
        mic_id = None  # 获取不到，不再负责麦克风
        out_id = self.outCombo.currentData()
        mon_id = self.monCombo.currentData()

        # if mic_id is not None and out_id is not None:
        if out_id is not None:
            self.deviceChanged.emit(-1, out_id, mon_id)  # -1 as placeholder for mic

    def autoSelectCableOutput(self):
        """
        尝试自动选择 CABLE Output 设备。
        """
        for i in range(self.outCombo.count()):
            text = self.outCombo.itemText(i).lower()
            if "cable" in text or "virtual" in text or "vb-audio" in text:
                self.outCombo.setCurrentIndex(i)
                return True
        return False

    def get_selected_ids(self):
        # mic_id = self.micCombo.currentData()
        mic_id = None
        return mic_id, self.outCombo.currentData(), self.monCombo.currentData()
