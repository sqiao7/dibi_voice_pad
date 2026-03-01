import sounddevice as sd
import psutil
import os
import win32gui
import win32process
import win32ui
import win32api
import win32con
import traceback
from PyQt6.QtGui import QIcon, QPixmap, QImage
from PyQt6.QtCore import QBuffer, QIODevice
import io


class DeviceManager:
    @staticmethod
    def get_input_devices():
        """
        返回输入设备（麦克风）列表。
        过滤逻辑：优先显示 Windows WASAPI 设备，如果不存在则显示 MME/DirectSound。
        实际上，简单的方法是按名称去重，或者只显示特定 HostAPI。
        Windows 上 HostAPI 索引通常：0=MME, 1=DirectSound, 2=WASAPI, 3=WDM-KS, 4=ASIO
        我们优先选择 MME (兼容性最好) 或者 WASAPI (性能最好)。
        鉴于用户反馈设备过多，我们只显示 MME 设备（通常是系统声音设置里看到的那些）。
        """
        devices = []
        try:
            # 获取所有 HostAPI 信息
            hostapis = sd.query_hostapis()
            target_api_index = -1

            # 优先寻找 MME，因为它显示的名称最接近 Windows 设置
            for i, api in enumerate(hostapis):
                if api["name"] == "MME":
                    target_api_index = i
                    break

            # 如果找不到 MME，尝试 WASAPI
            if target_api_index == -1:
                for i, api in enumerate(hostapis):
                    if "WASAPI" in api["name"]:
                        target_api_index = i
                        break

            for i, dev in enumerate(sd.query_devices()):
                # 过滤：必须是输入设备
                if dev["max_input_channels"] > 0:
                    # 过滤：必须匹配目标 HostAPI (如果找到了)
                    if target_api_index != -1 and dev["hostapi"] != target_api_index:
                        continue

                    devices.append({"id": i, "name": dev["name"], "hostapi": dev["hostapi"], "info": dev})
        except Exception as e:
            print(f"列出输入设备时出错: {e}")
            traceback.print_exc()
        return devices

    @staticmethod
    def get_output_devices():
        """
        返回输出设备列表。
        同样只显示 MME 设备以减少重复。
        """
        devices = []
        try:
            hostapis = sd.query_hostapis()
            target_api_index = -1

            for i, api in enumerate(hostapis):
                if api["name"] == "MME":
                    target_api_index = i
                    break

            if target_api_index == -1:
                for i, api in enumerate(hostapis):
                    if "WASAPI" in api["name"]:
                        target_api_index = i
                        break

            for i, dev in enumerate(sd.query_devices()):
                if dev["max_output_channels"] > 0:
                    if target_api_index != -1 and dev["hostapi"] != target_api_index:
                        continue
                    devices.append({"id": i, "name": dev["name"], "hostapi": dev["hostapi"], "info": dev})
        except Exception as e:
            print(f"列出输出设备时出错: {e}")
            traceback.print_exc()
        return devices

    @staticmethod
    def get_audio_processes():
        """
        返回潜在的音频进程列表。
        只列出具有可见窗口标题的进程。
        """
        processes = []
        try:
            current_pid = os.getpid()

            # 获取所有可见窗口及其 PID
            window_pids = {}

            def enum_window_callback(hwnd, _):
                try:
                    if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowTextLength(hwnd) > 0:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        title = win32gui.GetWindowText(hwnd)
                        # 如果同一个 PID 有多个窗口，保留标题最长的那个（通常是主窗口）
                        if pid not in window_pids or len(title) > len(window_pids[pid]):
                            window_pids[pid] = title
                except Exception:
                    # 忽略单个窗口处理时的错误
                    pass

            win32gui.EnumWindows(enum_window_callback, None)

            # 使用 try-except 包裹 process_iter，防止某些受保护进程导致 AccessDenied
            for proc in psutil.process_iter(["pid", "name", "exe"]):
                try:
                    pid = proc.info["pid"]
                    if pid == current_pid:
                        continue

                    # 简单过滤：跳过系统进程
                    if pid < 4:
                        continue

                    # 只包含有可见窗口标题的进程
                    if pid in window_pids:
                        title = window_pids[pid]
                        # 确保 exe 存在，如果不存在（AccessDenied）可能会在 info['exe'] 时抛出
                        exe_path = proc.info.get("exe", "")

                        processes.append({"pid": pid, "name": proc.info["name"], "title": title, "exe": exe_path})
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception:
                    # 忽略其他单个进程处理错误
                    continue

            # 按窗口标题排序
            processes.sort(key=lambda x: x["title"].lower())

        except Exception as e:
            print(f"获取音频进程列表时出错: {e}")
            traceback.print_exc()

        return processes

    @staticmethod
    def check_virtual_audio_device_installed():
        """
        检查是否安装了虚拟音频设备（如 VB-Cable）。
        """
        devices = DeviceManager.get_output_devices()
        for dev in devices:
            name = dev["name"].lower()
            if "cable" in name or "virtual" in name or "vb-audio" in name:
                return True
        return False

    @staticmethod
    def get_file_icon(path):
        """
        从可执行文件路径提取图标并返回 QIcon。
        """
        if not path or not os.path.exists(path):
            return None

        try:
            # 尝试使用 QFileIconProvider (最简单且兼容性好的方法)
            from PyQt6.QtWidgets import QFileIconProvider
            from PyQt6.QtCore import QFileInfo

            provider = QFileIconProvider()
            icon = provider.icon(QFileInfo(path))
            return icon
        except Exception:
            return None

    @staticmethod
    def get_default_device(device_type="output"):
        """
        获取系统默认音频设备名称 (使用 sounddevice 查询 default)
        注意：sounddevice.default.device 返回的是索引，query_devices 可以获取详情
        """
        try:
            # sd.default.device 返回 (input_idx, output_idx)
            idx = sd.default.device[0] if device_type == "input" else sd.default.device[1]
            if idx >= 0:
                info = sd.query_devices(idx)
                return info
        except Exception as e:
            print(f"Error getting default device: {e}")
        return None
