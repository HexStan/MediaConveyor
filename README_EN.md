# MediaConveyor

English | [中文](README.md)

**MediaConveyor** is a lightweight, Python-based automation tool designed to monitor specified directories for audio and video files and automatically process them using FFmpeg once they are fully written. It is ideal for scenarios requiring automated audio and video transcoding, compression, or format conversion.

📝 [Changelog](./CHANGELOG.md)

## 💡 Inspiration & Background

This project is inspired by the `autovideoconverter` feature in the [jlesage/docker-handbrake](https://github.com/jlesage/docker-handbrake) project, borrowing its core logic. I developed this project because HandBrake has poor support for VAAPI and AMD GPU proprietary drivers on Linux.

## ✨ Features

- **Directory Monitoring**: Supports continuous directory monitoring or running as a one-off script.
- **Multi-Task Support**: Define multiple independent monitoring and processing tasks within a single configuration file.
- **File Stability Detection**: Ensures only fully written files are processed by checking file modification times and size changes, preventing incomplete files from being processed during download or copying.
- **Custom FFmpeg Commands**: Fully customizable FFmpeg processing commands to meet various audio and video processing needs.
- **State Management**: Automatically records processed files to prevent duplicate processing.
- **Auto Archiving**: Automatically moves source files to a specified archive directory after processing is complete.
- **Docker Support**: Includes a Dockerfile and docker-compose.yml for quick containerized deployment.

## 🛠️ Requirements

- **Python 3.x**
- **FFmpeg**: Must be installed and configured in the system's environment variables (PATH).

## 🚀 Installation & Usage

### Method 1: Run Directly

1. **Clone the Repository**
   ```bash
   git clone https://github.com/HexStan/MediaConveyor.git
   cd MediaConveyor
   ```

2. **Install Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Prepare Configuration File**
   Copy the example configuration file and modify it as needed:
   ```bash
   cp config/config.toml.example config/config.toml
   ```

4. **Run the Program**
   ```bash
   python main.py
   ```

### Method 2: Use Docker

1. **Prepare Configuration File**
   ```bash
   cp config/config.toml.example config/config.toml
   ```

2. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```
