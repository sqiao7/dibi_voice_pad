import PyInstaller.__main__
import os
import shutil
from PyInstaller.utils.hooks import collect_data_files


def build():
    app_name = "DIBIVoicePad"
    entry_point = "main.py"

    # Clean previous builds
    if os.path.exists("build"):
        try:
            shutil.rmtree("build")
        except Exception as e:
            print(f"Warning: Could not clean build directory: {e}")

    if os.path.exists("dist"):
        try:
            shutil.rmtree("dist")
        except Exception as e:
            print(f"Warning: Could not clean dist directory: {e}")

    # Collect qfluentwidgets data
    # qfluentwidgets relies on images and qss files
    # We use collect_data_files to find them
    try:
        qfw_datas = collect_data_files("qfluentwidgets")
    except Exception as e:
        print(f"Warning: Could not collect qfluentwidgets data: {e}")
        qfw_datas = []

    # Prepare --add-data arguments
    # PyInstaller expects 'source;dest' on Windows
    add_data_args = []
    for source, dest in qfw_datas:
        # dest in collect_data_files is relative to the package root usually
        # PyInstaller --add-data takes "source;dest"
        add_data_args.append(f"--add-data={source};{dest}")

    # Also add our own assets
    # Ensure assets directory exists
    if os.path.exists("assets"):
        add_data_args.append("--add-data=assets;assets")

    # PyInstaller arguments
    args = [
        entry_point,
        f"--name={app_name}",
        "--onefile",
        "--noconsole",
        # Use absolute path for icon to avoid ambiguity
        f"--icon={os.path.abspath('assets/icon.ico')}",
        "--clean",
        "--distpath=dist",
        "--workpath=build",
        # Force overwrite
        "-y",
    ] + add_data_args

    print(f"Building {app_name} with PyInstaller...")
    print("Arguments:", args)

    PyInstaller.__main__.run(args)
    print("Build complete.")


if __name__ == "__main__":
    if not os.path.exists("assets"):
        print("Warning: 'assets' directory missing.")

    build()
