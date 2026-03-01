import json
import os

class ConfigManager:
    CONFIG_FILE = "config.json"
    DEFAULT_CONFIG = {
        "mic_name": "",
        "out_name": "",
        "mon_name": "",
        "monitor_enabled": False,
        "proc_vol": 1.0,
        "mic_vol": 1.0,
        "proc_mute": False,
        "mic_mute": False,
        "close_behavior": "minimize"
    }

    @staticmethod
    def load_config():
        if os.path.exists(ConfigManager.CONFIG_FILE):
            try:
                with open(ConfigManager.CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    config = ConfigManager.DEFAULT_CONFIG.copy()
                    config.update(data)
                    return config
            except Exception as e:
                print(f"加载配置失败: {e}")
        return ConfigManager.DEFAULT_CONFIG.copy()

    @staticmethod
    def save_config(config):
        try:
            with open(ConfigManager.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            print("配置已保存")
        except Exception as e:
            print(f"保存配置失败: {e}")
