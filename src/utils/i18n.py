import json
import os


class I18n:
    _instance = None

    LANGUAGES = {"zh_CN": "简体中文", "en_US": "English"}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(I18n, cls).__new__(cls)
            cls._instance.current_lang = "zh_CN"
            cls._instance.listeners = []
            cls._instance._init_translations()
        return cls._instance

    def _init_translations(self):
        self.translations = {
            "zh_CN": {
                # MainWindow
                "app_name": "DIBI 进程音频融合",
                "app_name_mixing": "DIBI 进程音频融合 (混音中)",
                "mixer": "混音器",
                "playlist": "音乐列表",
                "settings": "设置",
                "start_mixing": "开始混音",
                "stop_mixing": "停止混音",
                "started": "已启动",
                "engine_running": "混音引擎正在运行",
                "show_main_window": "显示主界面",
                "exit": "退出",
                "minimized_to_tray": "程序已最小化到托盘运行",
                "select_device_first": "请先选择设备。",
                "mic_device_changed": "麦克风设备变更",
                "output_device_changed": "输出设备变更",
                # MixerInterface
                "mixer_console": "混音台",
                "select_process": "请选择要捕获的音频源进程...",
                "refresh_process": "刷新进程列表",
                "select_mic": "请选择麦克风...",
                "refresh_mic": "刷新麦克风列表",
                "app_volume": "应用音量",
                "app_volume_desc": "调节选中进程的音量",
                "mic_volume": "麦克风音量",
                "mic_volume_desc": "调节麦克风输入音量",
                "music_volume": "音乐音量",
                "music_volume_desc": "调节播放列表音乐音量",
                "monitor_on": "开启监听",
                "monitor_off": "关闭监听",
                "monitor_tooltip_on": "关闭监听",
                "monitor_tooltip_off": "开启监听",
                "mute_tooltip": "点击静音",
                "unmute_tooltip": "取消静音",
                # MusicInterface
                "playlist_title": "播放列表",
                "add_files": "添加文件",
                "remove_selected": "移除选中",
                "monitor": "监听",
                "monitor_global_tooltip": "开启/关闭 全局监听 (听见播放的声音)",
                "select_files_dialog": "选择音频/视频文件",
                "play": "播放",
                "rename": "重命名",
                "remove": "移除",
                "enter_new_name": "请输入新名称:",
                "error": "错误",
                "rename_failed": "重命名失败: {}\n文件可能正在被使用。",
                "delete_failed": "删除文件失败: {}\n文件可能正在被使用。",
                "file_in_use": "文件可能正在被使用。",
                # SettingInterface
                "settings_title": "设置",
                "language": "语言",
                "interface_language": "界面语言",
                "main_output": "主输出设备 (推流目标):",
                "main_output_desc": "请选择虚拟音频线 (如 VB-Cable Input)。如果选择扬声器/耳机，您将直接听到声音且无法通过监听开关控制。",
                "local_monitor": "本地监听设备 (耳机/扬声器):",
                "close_behavior": "点击关闭按钮时:",
                "minimize_tray": "最小化到系统托盘",
                "exit_app": "退出程序",
                "advanced": "高级设置:",
                "open_log": "打开日志目录",
                "open_config": "打开配置文件",
                "refresh_devices": "刷新设备列表",
                "no_virtual_device": "未检测到虚拟音频设备",
                "virtual_device_warning": "为了实现最佳的混音和推流效果，建议安装 VB-Cable 虚拟音频驱动。\n如果使用扬声器作为主输出，您将无法分离监听和混音输出。",
                "download_driver": "点击下载 VB-Cable 驱动",
                "virtual_device_warning_title": "未检测到虚拟音频设备",
                "about": "关于",
                "about_desc": "DIBI 进程音频融合工具，旨在帮助主播和内容创作者轻松管理多路音频源。",
                "visit_website": "访问官网",
                "visit_github": "GitHub",
            },
            "en_US": {
                # MainWindow
                "app_name": "DIBI Voice Pad",
                "app_name_mixing": "DIBI Voice Pad (Mixing)",
                "mixer": "Mixer",
                "playlist": "Playlist",
                "settings": "Settings",
                "start_mixing": "Start Mixing",
                "stop_mixing": "Stop Mixing",
                "started": "Started",
                "engine_running": "Mixing Engine is running",
                "show_main_window": "Show Main Window",
                "exit": "Exit",
                "minimized_to_tray": "App minimized to tray",
                "select_device_first": "Please select devices first.",
                "mic_device_changed": "Mic Device Changed",
                "output_device_changed": "Output Device Changed",
                # MixerInterface
                "mixer_console": "Mixer Console",
                "select_process": "Select audio source process...",
                "refresh_process": "Refresh Process List",
                "select_mic": "Select Microphone...",
                "refresh_mic": "Refresh Microphone List",
                "app_volume": "App Volume",
                "app_volume_desc": "Adjust process volume",
                "mic_volume": "Mic Volume",
                "mic_volume_desc": "Adjust mic volume",
                "music_volume": "Music Volume",
                "music_volume_desc": "Adjust music volume",
                "monitor_on": "Monitor On",
                "monitor_off": "Monitor Off",
                "monitor_tooltip_on": "Turn Off Monitor",
                "monitor_tooltip_off": "Turn On Monitor",
                "mute_tooltip": "Mute",
                "unmute_tooltip": "Unmute",
                # MusicInterface
                "playlist_title": "Playlist",
                "add_files": "Add Files",
                "remove_selected": "Remove Selected",
                "monitor": "Monitor",
                "monitor_global_tooltip": "Toggle global monitor (Hear playback)",
                "select_files_dialog": "Select Audio/Video Files",
                "play": "Play",
                "rename": "Rename",
                "remove": "Remove",
                "enter_new_name": "Enter new name:",
                "error": "Error",
                "rename_failed": "Rename failed: {}\nFile might be in use.",
                "delete_failed": "Delete failed: {}\nFile might be in use.",
                "file_in_use": "File might be in use.",
                # SettingInterface
                "settings_title": "Settings",
                "language": "Language",
                "interface_language": "Interface Language",
                "main_output": "Main Output (Stream Target):",
                "main_output_desc": "Select Virtual Audio Cable (e.g. VB-Cable Input). Selecting speakers/headphones mixes sound directly.",
                "local_monitor": "Local Monitor (Headphones/Speakers):",
                "close_behavior": "When closing window:",
                "minimize_tray": "Minimize to Tray",
                "exit_app": "Exit App",
                "advanced": "Advanced:",
                "open_log": "Open Log Dir",
                "open_config": "Open Config File",
                "refresh_devices": "Refresh Devices",
                "no_virtual_device": "No Virtual Audio Device",
                "virtual_device_warning": "For best results, install VB-Cable driver.\nUsing speakers as main output prevents separating monitor and mix output.",
                "download_driver": "Download VB-Cable Driver",
                "virtual_device_warning_title": "No Virtual Audio Device",
                "about": "About",
                "about_desc": "DIBI Voice Pad, designed to help streamers and creators manage multiple audio sources easily.",
                "visit_website": "Visit Website",
                "visit_github": "GitHub",
            },
        }

    def set_language(self, lang_code):
        if lang_code in self.translations:
            self.current_lang = lang_code
            self.notify_listeners()

    def get_language(self):
        return self.current_lang

    def t(self, key):
        lang_data = self.translations.get(self.current_lang, self.translations["zh_CN"])  # Default to zh_CN if lang missing
        return lang_data.get(key, key)

    def add_listener(self, listener_func):
        if listener_func not in self.listeners:
            self.listeners.append(listener_func)

    def remove_listener(self, listener_func):
        if listener_func in self.listeners:
            self.listeners.remove(listener_func)

    def notify_listeners(self):
        for listener in self.listeners:
            try:
                listener()
            except Exception as e:
                print(f"Error notifying translation listener: {e}")


# Global instance
tr = I18n()
