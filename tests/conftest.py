import os
import sqlite3
import sys
import tempfile
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        yield tmp


@pytest.fixture
def sample_toml_path(temp_dir):
    content = """[global]
scan_interval = 30
log_dir = "test_logs"
max_log_files = 5
log_level = "DEBUG"

[[tasks]]
name = "Test Task"
source_dir = "./source"
dest_dir = "./dest"
backup_dir = "./backup"
ffmpeg_cmd = "ffmpeg -i {input} {output}.mp4"
ffmpeg_cmd_fallback = "ffmpeg -i {input} {output}_fallback.mp4"
stable_duration = 5
failure_count = 5
fallback_count = 3

[tasks.filter]
include_patterns = ["*.mp4", "*.mkv", "*.txt"]
exclude_patterns = ["*.tmp"]
passthrough_patterns = ["*.txt"]
file_mtime = 300
size = { min = "1MB", max = "10GB" }
duration = { min = "5s", max = "3600s" }
video_bitrate = { min = "500Kbps" }
audio_bitrate = { max = "320Kbps" }
total_bitrate = { min = "1Mbps", max = "30Mbps" }
framerate = { min = 24, max = 60 }
short_side = { min = 720, max = 1080 }
exclude_video_codecs = ["hevc", "av1"]
exclude_audio_codecs = ["opus"]
"""
    path = os.path.join(temp_dir, "config.toml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


@pytest.fixture
def minimal_toml_path(temp_dir):
    content = """[global]
scan_interval = 0

[[tasks]]
source_dir = "./source"
dest_dir = "./dest"
backup_dir = "./backup"
ffmpeg_cmd = "ffmpeg -i {input} {output}.mp4"
"""
    path = os.path.join(temp_dir, "config.toml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


@pytest.fixture
def sample_db(temp_dir):
    return os.path.join(temp_dir, "media-conveyor.db")


@pytest.fixture
def sample_db_with_data(temp_dir):
    path = os.path.join(temp_dir, "media-conveyor.db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS file_state ("
        "    filepath              TEXT PRIMARY KEY,"
        "    success_time          REAL,"
        "    failure_count         INTEGER NOT NULL DEFAULT 0,"
        "    ffmpeg_failure_count  INTEGER NOT NULL DEFAULT 0"
        ")"
    )
    conn.execute(
        "INSERT INTO file_state (filepath, failure_count, ffmpeg_failure_count)"
        " VALUES (?, ?, ?)",
        ("/test/file1.mp4", 2, 1),
    )
    conn.execute(
        "INSERT INTO file_state (filepath, success_time, failure_count, ffmpeg_failure_count)"
        " VALUES (?, ?, 0, 0)",
        ("/test/file2.mp4", 1234567890.0),
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def basic_media_info():
    return {
        "duration": 120.5,
        "size": 52428800,
        "total_bitrate": 5000000,
        "video_bitrate": 3000000,
        "audio_bitrate": 192000,
        "framerate": 30.0,
        "short_side": 1080,
        "video_codec": "h264",
        "audio_codec": "aac",
    }


@pytest.fixture
def basic_filter_config():
    return {
        "include_patterns": ["*.mp4", "*.mkv", "*.txt"],
        "exclude_patterns": ["*.tmp"],
        "passthrough_patterns": ["*.txt"],
        "file_mtime": 300,
        "size": {"min": "1MB", "max": "10GB"},
        "duration": {"min": "5s", "max": "3600s"},
        "video_bitrate": {"min": "500Kbps"},
        "audio_bitrate": {"max": "320Kbps"},
        "total_bitrate": {"min": "1Mbps", "max": "30Mbps"},
        "framerate": {"min": 24, "max": 60},
        "short_side": {"min": 720, "max": 1080},
        "exclude_video_codecs": ["hevc", "av1"],
        "exclude_audio_codecs": ["opus"],
    }
