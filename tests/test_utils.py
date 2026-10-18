import json
import os
from unittest.mock import MagicMock, patch

import pytest

from src.utils import clean_empty_dirs, get_media_duration, get_media_info

FFPROBE_OUTPUT = {
    "format": {
        "duration": "120.5",
        "bit_rate": "5000000",
    },
    "streams": [
        {
            "codec_type": "video",
            "codec_name": "h264",
            "bit_rate": "3000000",
            "width": 1920,
            "height": 1080,
            "avg_frame_rate": "30/1",
        },
        {
            "codec_type": "audio",
            "codec_name": "aac",
            "bit_rate": "192000",
        },
    ],
}


class TestGetMediaInfo:
    def test_returns_defaults_for_nonexistent_file(self):
        with patch("os.path.exists", return_value=False):
            info = get_media_info("/nonexistent/file.mp4")
            assert info["duration"] == 0.0
            assert info["size"] == 0
            assert info["video_codec"] == ""

    def test_parses_ffprobe_output(self, temp_dir):
        test_file = os.path.join(temp_dir, "test.mp4")
        with open(test_file, "wb") as f:
            f.write(b"\x00" * 1000)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(FFPROBE_OUTPUT)

        with patch("subprocess.run", return_value=mock_result):
            info = get_media_info(test_file)
            assert info["duration"] == 120.5
            assert info["size"] == 1000
            assert info["total_bitrate"] == 5000000.0
            assert info["video_bitrate"] == 3000000.0
            assert info["audio_bitrate"] == 192000.0
            assert info["framerate"] == 30.0
            assert info["short_side"] == 1080
            assert info["video_codec"] == "h264"
            assert info["audio_codec"] == "aac"

    def test_handles_missing_duration(self, temp_dir):
        test_file = os.path.join(temp_dir, "test.mp4")
        with open(test_file, "wb") as f:
            f.write(b"\x00" * 500)

        output = {"format": {}, "streams": []}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(output)

        with patch("subprocess.run", return_value=mock_result):
            info = get_media_info(test_file)
            assert info["duration"] == 0.0
            assert info["size"] == 500

    def test_handles_ffprobe_failure(self, temp_dir):
        test_file = os.path.join(temp_dir, "test.mp4")
        with open(test_file, "wb") as f:
            f.write(b"\x00" * 200)

        with patch("subprocess.run", side_effect=Exception("ffprobe not found")):
            info = get_media_info(test_file)
            assert info["size"] == 200
            assert info["duration"] == 0.0

    def test_handles_ffprobe_nonzero_return(self, temp_dir):
        test_file = os.path.join(temp_dir, "test.mp4")
        with open(test_file, "wb") as f:
            f.write(b"\x00" * 300)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            info = get_media_info(test_file)
            assert info["size"] == 300
            assert info["duration"] == 0.0

    def test_handles_invalid_duration_string(self, temp_dir):
        test_file = os.path.join(temp_dir, "test.mp4")
        with open(test_file, "wb") as f:
            f.write(b"\x00" * 100)

        output = {"format": {"duration": "not_a_number"}, "streams": []}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(output)

        with patch("subprocess.run", return_value=mock_result):
            info = get_media_info(test_file)
            assert info["duration"] == 0.0

    def test_handles_invalid_bit_rate_string(self, temp_dir):
        test_file = os.path.join(temp_dir, "test.mp4")
        with open(test_file, "wb") as f:
            f.write(b"\x00" * 100)

        output = {"format": {"bit_rate": "invalid"}, "streams": []}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(output)

        with patch("subprocess.run", return_value=mock_result):
            info = get_media_info(test_file)
            assert info["total_bitrate"] == 0

    def test_handles_ffprobe_timeout(self, temp_dir):
        test_file = os.path.join(temp_dir, "test.mp4")
        with open(test_file, "wb") as f:
            f.write(b"\x00" * 100)

        with patch("subprocess.run", side_effect=Exception("timeout")):
            info = get_media_info(test_file)
            assert info["size"] == 100

    def test_framerate_with_r_frame_rate_fallback(self, temp_dir):
        test_file = os.path.join(temp_dir, "test.mp4")
        with open(test_file, "wb") as f:
            f.write(b"\x00" * 100)

        output = {
            "format": {},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "r_frame_rate": "24000/1001",
                    "width": 1920,
                    "height": 1080,
                }
            ],
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(output)

        with patch("subprocess.run", return_value=mock_result):
            info = get_media_info(test_file)
            assert pytest.approx(info["framerate"], rel=1e-3) == 24000 / 1001

    def test_size_oserror_handled(self):
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.getsize", side_effect=OSError("permission denied")),
            patch("subprocess.run", side_effect=Exception("skip ffprobe")),
        ):
            info = get_media_info("/fake/file.mp4")
            assert info["size"] == 0

    def test_zero_division_in_framerate_handled(self, temp_dir):
        test_file = os.path.join(temp_dir, "test.mp4")
        with open(test_file, "wb") as f:
            f.write(b"\x00" * 100)

        output = {
            "format": {},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "avg_frame_rate": "24/0",
                    "width": 1920,
                    "height": 1080,
                }
            ],
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(output)

        with patch("subprocess.run", return_value=mock_result):
            info = get_media_info(test_file)
            assert info["framerate"] == 0.0

    def test_framerate_without_slash(self, temp_dir):
        test_file = os.path.join(temp_dir, "test.mp4")
        with open(test_file, "wb") as f:
            f.write(b"\x00" * 100)

        output = {
            "format": {},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "avg_frame_rate": "30",
                    "width": 1920,
                    "height": 1080,
                }
            ],
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(output)

        with patch("subprocess.run", return_value=mock_result):
            info = get_media_info(test_file)
            assert info["framerate"] == 0.0

    def test_multiple_streams_first_takes_priority(self, temp_dir):
        test_file = os.path.join(temp_dir, "test.mp4")
        with open(test_file, "wb") as f:
            f.write(b"\x00" * 100)

        output = {
            "format": {},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                },
                {
                    "codec_type": "video",
                    "codec_name": "mpeg4",
                    "width": 720,
                    "height": 480,
                },
                {"codec_type": "audio", "codec_name": "aac", "bit_rate": "128000"},
                {"codec_type": "audio", "codec_name": "mp3", "bit_rate": "192000"},
            ],
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(output)

        with patch("subprocess.run", return_value=mock_result):
            info = get_media_info(test_file)
            assert info["video_codec"] == "h264"
            assert info["audio_codec"] == "aac"


class TestGetMediaDuration:
    def test_delegates_to_get_media_info(self):
        with patch("src.utils.get_media_info", return_value={"duration": 45.0}):
            assert get_media_duration("/fake/file.mp4") == 45.0

    def test_returns_zero_when_no_duration(self):
        with patch("src.utils.get_media_info", return_value={}):
            assert get_media_duration("/fake/file.mp4") == 0.0


class TestCleanEmptyDirs:
    def test_nonexistent_directory_no_error(self):
        clean_empty_dirs("/nonexistent/path")

    def test_removes_empty_subdirs(self, temp_dir):
        sub = os.path.join(temp_dir, "empty_sub")
        os.makedirs(sub)
        clean_empty_dirs(temp_dir)
        assert not os.path.exists(sub)

    def test_preserves_root_directory(self, temp_dir):
        os.makedirs(os.path.join(temp_dir, "empty_sub"))
        clean_empty_dirs(temp_dir)
        assert os.path.exists(temp_dir)

    def test_preserves_nonempty_subdirs(self, temp_dir):
        sub = os.path.join(temp_dir, "nonempty_sub")
        os.makedirs(sub)
        with open(os.path.join(sub, "file.txt"), "w") as f:
            f.write("data")
        clean_empty_dirs(temp_dir)
        assert os.path.exists(sub)

    def test_handles_nested_empty_dirs(self, temp_dir):
        deep = os.path.join(temp_dir, "a", "b", "c")
        os.makedirs(deep)
        os.makedirs(os.path.join(temp_dir, "a", "d"))
        clean_empty_dirs(temp_dir)
        assert not os.path.exists(os.path.join(temp_dir, "a"))

    def test_handles_oserror_gracefully(self, temp_dir):
        sub = os.path.join(temp_dir, "empty_sub")
        os.makedirs(sub)
        with patch("os.rmdir", side_effect=OSError):
            clean_empty_dirs(temp_dir)
