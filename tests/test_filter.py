import pytest

from src.filter import (
    FileFilter,
    parse_bitrate,
    parse_size,
    parse_timespan,
)


class TestParseSize:
    def test_zero_for_falsy(self):
        assert parse_size(None) == 0
        assert parse_size("") == 0
        assert parse_size(0) == 0

    def test_int_returns_float(self):
        assert parse_size(1024) == 1024.0

    def test_float_passthrough(self):
        assert parse_size(1024.5) == 1024.5

    def test_humanfriendly_string(self):
        assert parse_size("1MB") == 1000000
        assert parse_size("1MiB") == 1048576


class TestParseTimespan:
    def test_zero_for_falsy(self):
        assert parse_timespan(None) == 0
        assert parse_timespan("") == 0

    def test_int_returns_float(self):
        assert parse_timespan(60) == 60.0

    def test_humanfriendly_string(self):
        assert parse_timespan("60s") == 60.0
        assert parse_timespan("2h") == 7200.0

    def test_invalid_string_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_timespan("invalid_timespan_string")


class TestParseBitrate:
    def test_zero_for_falsy(self):
        assert parse_bitrate(None) == 0
        assert parse_bitrate("") == 0

    def test_int_returns_float(self):
        assert parse_bitrate(500000) == 500000.0

    def test_kbps_suffix(self):
        assert parse_bitrate("500Kbps") == 500 * 1024
        assert parse_bitrate("500K") == 500 * 1024

    def test_mbps_suffix(self):
        assert parse_bitrate("1Mbps") == 1 * 1024 * 1024
        assert parse_bitrate("1M") == 1 * 1024 * 1024

    def test_bps_suffix(self):
        assert parse_bitrate("1000bps") == 1000.0

    def test_case_insensitive(self):
        assert parse_bitrate("500kbps") == 500 * 1024
        assert parse_bitrate("1mbps") == 1 * 1024 * 1024

    def test_fallback_humanfriendly(self):
        result = parse_bitrate("1MB")
        assert result == 1000000


class TestFileFilterInit:
    def test_default_values(self):
        ff = FileFilter({})
        assert ff.include_patterns == []
        assert ff.exclude_patterns == []
        assert ff.passthrough_patterns == []
        assert ff.file_mtime == 0
        assert ff.size_min == 0
        assert ff.size_max == 0
        assert ff.duration_min == 0
        assert ff.duration_max == 0
        assert ff.framerate_min == 0.0
        assert ff.framerate_max == 0.0
        assert ff.short_side_min == 0
        assert ff.short_side_max == 0
        assert ff.exclude_vcodecs == []
        assert ff.exclude_acodecs == []

    def test_full_config(self, basic_filter_config):
        ff = FileFilter(basic_filter_config)
        assert ff.include_patterns == ["*.mp4", "*.mkv", "*.txt"]
        assert ff.exclude_patterns == ["*.tmp"]
        assert ff.passthrough_patterns == ["*.txt"]
        assert ff.file_mtime == 300
        assert ff.size_min > 0
        assert ff.size_max > 0
        assert ff.duration_min > 0
        assert ff.duration_max > 0
        assert ff.v_bitrate_min > 0
        assert ff.v_bitrate_max == 0
        assert ff.a_bitrate_max > 0
        assert ff.exclude_vcodecs == ["hevc", "av1"]
        assert ff.exclude_acodecs == ["opus"]


class TestFileFilterMatch:
    def test_pass_all_criteria(self, basic_filter_config, basic_media_info):
        ff = FileFilter(basic_filter_config)
        assert ff.match(basic_media_info) is True

    def test_fail_size_min(self, basic_filter_config):
        ff = FileFilter(basic_filter_config)
        info = {
            "size": 100,
            "duration": 120,
            "total_bitrate": 5000000,
            "video_bitrate": 3000000,
            "audio_bitrate": 192000,
            "framerate": 30,
            "short_side": 1080,
            "video_codec": "h264",
            "audio_codec": "aac",
        }
        assert ff.match(info) is False

    def test_fail_size_max(self, basic_filter_config):
        ff = FileFilter(basic_filter_config)
        ff.size_max = parse_size("100MB")
        info = {
            "size": 200 * 1024 * 1024,
            "duration": 120,
            "total_bitrate": 5000000,
            "video_bitrate": 3000000,
            "audio_bitrate": 192000,
            "framerate": 30,
            "short_side": 1080,
            "video_codec": "h264",
            "audio_codec": "aac",
        }
        assert ff.match(info) is False

    def test_fail_duration_min(self, basic_filter_config):
        ff = FileFilter(basic_filter_config)
        info = {
            "size": 52428800,
            "duration": 1,
            "total_bitrate": 5000000,
            "video_bitrate": 3000000,
            "audio_bitrate": 192000,
            "framerate": 30,
            "short_side": 1080,
            "video_codec": "h264",
            "audio_codec": "aac",
        }
        assert ff.match(info) is False

    def test_fail_duration_max(self, basic_filter_config):
        ff = FileFilter(basic_filter_config)
        info = {
            "size": 52428800,
            "duration": 50000,
            "total_bitrate": 5000000,
            "video_bitrate": 3000000,
            "audio_bitrate": 192000,
            "framerate": 30,
            "short_side": 1080,
            "video_codec": "h264",
            "audio_codec": "aac",
        }
        assert ff.match(info) is False

    def test_fail_total_bitrate_min(self, basic_filter_config):
        ff = FileFilter(basic_filter_config)
        info = {
            "size": 52428800,
            "duration": 120,
            "total_bitrate": 100,
            "video_bitrate": 3000000,
            "audio_bitrate": 192000,
            "framerate": 30,
            "short_side": 1080,
            "video_codec": "h264",
            "audio_codec": "aac",
        }
        assert ff.match(info) is False

    def test_fail_total_bitrate_max(self, basic_filter_config):
        ff = FileFilter(basic_filter_config)
        info = {
            "size": 52428800,
            "duration": 120,
            "total_bitrate": 100000000,
            "video_bitrate": 3000000,
            "audio_bitrate": 192000,
            "framerate": 30,
            "short_side": 1080,
            "video_codec": "h264",
            "audio_codec": "aac",
        }
        assert ff.match(info) is False

    def test_fail_video_bitrate_min(self, basic_filter_config):
        ff = FileFilter(basic_filter_config)
        info = {
            "size": 52428800,
            "duration": 120,
            "total_bitrate": 5000000,
            "video_bitrate": 100,
            "audio_bitrate": 192000,
            "framerate": 30,
            "short_side": 1080,
            "video_codec": "h264",
            "audio_codec": "aac",
        }
        assert ff.match(info) is False

    def test_fail_video_bitrate_max(self, basic_filter_config):
        ff = FileFilter({"video_bitrate": {"max": "10Mbps"}})
        info = {
            "size": 52428800,
            "duration": 120,
            "total_bitrate": 5000000,
            "video_bitrate": 20000000,
            "audio_bitrate": 192000,
            "framerate": 30,
            "short_side": 1080,
            "video_codec": "h264",
            "audio_codec": "aac",
        }
        assert ff.match(info) is False

    def test_fail_audio_bitrate_min(self, basic_filter_config):
        ff = FileFilter({"audio_bitrate": {"min": "320Kbps"}})
        info = {
            "size": 52428800,
            "duration": 120,
            "total_bitrate": 5000000,
            "video_bitrate": 3000000,
            "audio_bitrate": 64000,
            "framerate": 30,
            "short_side": 1080,
            "video_codec": "h264",
            "audio_codec": "aac",
        }
        assert ff.match(info) is False

    def test_fail_audio_bitrate_max(self, basic_filter_config):
        ff = FileFilter(basic_filter_config)
        ff.a_bitrate_max = parse_bitrate("128Kbps")
        info = {
            "size": 52428800,
            "duration": 120,
            "total_bitrate": 5000000,
            "video_bitrate": 3000000,
            "audio_bitrate": 192000,
            "framerate": 30,
            "short_side": 1080,
            "video_codec": "h264",
            "audio_codec": "aac",
        }
        assert ff.match(info) is False

    def test_fail_framerate_min(self, basic_filter_config):
        ff = FileFilter(basic_filter_config)
        info = {
            "size": 52428800,
            "duration": 120,
            "total_bitrate": 5000000,
            "video_bitrate": 3000000,
            "audio_bitrate": 192000,
            "framerate": 10,
            "short_side": 1080,
            "video_codec": "h264",
            "audio_codec": "aac",
        }
        assert ff.match(info) is False

    def test_fail_framerate_max(self, basic_filter_config):
        ff = FileFilter(basic_filter_config)
        info = {
            "size": 52428800,
            "duration": 120,
            "total_bitrate": 5000000,
            "video_bitrate": 3000000,
            "audio_bitrate": 192000,
            "framerate": 120,
            "short_side": 1080,
            "video_codec": "h264",
            "audio_codec": "aac",
        }
        assert ff.match(info) is False

    def test_fail_short_side_min(self, basic_filter_config):
        ff = FileFilter(basic_filter_config)
        info = {
            "size": 52428800,
            "duration": 120,
            "total_bitrate": 5000000,
            "video_bitrate": 3000000,
            "audio_bitrate": 192000,
            "framerate": 30,
            "short_side": 480,
            "video_codec": "h264",
            "audio_codec": "aac",
        }
        assert ff.match(info) is False

    def test_fail_short_side_max(self, basic_filter_config):
        ff = FileFilter(basic_filter_config)
        info = {
            "size": 52428800,
            "duration": 120,
            "total_bitrate": 5000000,
            "video_bitrate": 3000000,
            "audio_bitrate": 192000,
            "framerate": 30,
            "short_side": 2160,
            "video_codec": "h264",
            "audio_codec": "aac",
        }
        assert ff.match(info) is False

    def test_fail_excluded_video_codec(self, basic_filter_config):
        ff = FileFilter(basic_filter_config)
        info = {
            "size": 52428800,
            "duration": 120,
            "total_bitrate": 5000000,
            "video_bitrate": 3000000,
            "audio_bitrate": 192000,
            "framerate": 30,
            "short_side": 1080,
            "video_codec": "hevc",
            "audio_codec": "aac",
        }
        assert ff.match(info) is False

    def test_fail_excluded_audio_codec(self, basic_filter_config):
        ff = FileFilter(basic_filter_config)
        info = {
            "size": 52428800,
            "duration": 120,
            "total_bitrate": 5000000,
            "video_bitrate": 3000000,
            "audio_bitrate": 192000,
            "framerate": 30,
            "short_side": 1080,
            "video_codec": "h264",
            "audio_codec": "opus",
        }
        assert ff.match(info) is False

    def test_fail_excluded_video_codec_case_insensitive(self, basic_filter_config):
        ff = FileFilter(basic_filter_config)
        info = {
            "size": 52428800,
            "duration": 120,
            "total_bitrate": 5000000,
            "video_bitrate": 3000000,
            "audio_bitrate": 192000,
            "framerate": 30,
            "short_side": 1080,
            "video_codec": "HEVC",
            "audio_codec": "aac",
        }
        assert ff.match(info) is False

    def test_match_with_logger_logs_debug(self, basic_filter_config):
        ff = FileFilter({"size": {"min": "1GB"}})
        mock_logger = type(
            "MockLogger",
            (),
            {"debug": lambda self, msg: setattr(self, "last_msg", msg)},
        )()
        info = {"size": 100}
        assert (
            ff.match(info, logger=mock_logger, rel_path="test.mp4", task_name="T1")
            is False
        )
        assert "T1" in mock_logger.last_msg
        assert "test.mp4" in mock_logger.last_msg

    def test_threshold_zero_skips_check(self):
        ff = FileFilter({})
        info = {
            "size": 0,
            "duration": 0,
            "total_bitrate": 0,
            "video_bitrate": 0,
            "audio_bitrate": 0,
            "framerate": 0,
            "short_side": 0,
            "video_codec": "",
            "audio_codec": "",
        }
        assert ff.match(info) is True


class TestFileFilterRequiresMediaInfo:
    def test_empty_config_requires_no_media_info(self):
        ff = FileFilter({})
        assert ff.requires_media_info() is False

    def test_size_only_requires_no_media_info(self):
        ff = FileFilter({"size": {"min": "1MB"}})
        assert ff.requires_media_info() is False

    def test_duration_filter_requires_media_info(self):
        ff = FileFilter({"duration": {"min": "5s"}})
        assert ff.requires_media_info() is True

    def test_bitrate_filter_requires_media_info(self):
        ff = FileFilter({"total_bitrate": {"min": "1M"}})
        assert ff.requires_media_info() is True

    def test_codec_exclusion_requires_media_info(self):
        ff = FileFilter({"exclude_video_codecs": ["hevc"]})
        assert ff.requires_media_info() is True

    def test_framerate_requires_media_info(self):
        ff = FileFilter({"framerate": {"min": 30}})
        assert ff.requires_media_info() is True


class TestFileFilterClassify:
    def test_no_patterns_process_all(self):
        ff = FileFilter({})
        assert ff.classify("video.mp4") == "process"
        assert ff.classify("sub/dir/anything.xyz") == "process"

    def test_include_match_by_extension(self):
        ff = FileFilter({"include_patterns": ["*.mp4", "*.mkv"]})
        assert ff.classify("video.mp4") == "process"
        assert ff.classify("video.mkv") == "process"
        assert ff.classify("video.avi") == "skip"

    def test_include_matches_files_in_subdirs(self):
        ff = FileFilter({"include_patterns": ["*.mp4"]})
        assert ff.classify("sub/dir/video.mp4") == "process"

    def test_include_directory_pattern_matches_all_levels(self):
        ff = FileFilter({"include_patterns": ["alpha/*"]})
        assert ff.classify("alpha/video.mp4") == "process"
        assert ff.classify("alpha/sub/deep/video.mp4") == "process"
        assert ff.classify("beta/video.mp4") == "skip"

    def test_include_directory_prefix_pattern(self):
        ff = FileFilter({"include_patterns": ["bravo*/*"]})
        assert ff.classify("bravo/video.mp4") == "process"
        assert ff.classify("bravo-2/video.mp4") == "process"
        assert ff.classify("charlie/video.mp4") == "skip"

    def test_include_substring_pattern(self):
        ff = FileFilter({"include_patterns": ["*charlie*.mp4"]})
        assert ff.classify("my-charlie-video.mp4") == "process"
        assert ff.classify("sub/charlie.mp4") == "process"
        assert ff.classify("charlie.mkv") == "skip"

    def test_exclude_overrides_include(self):
        ff = FileFilter(
            {"include_patterns": ["*.mp4"], "exclude_patterns": ["*sample*"]}
        )
        assert ff.classify("video.mp4") == "process"
        assert ff.classify("video-sample.mp4") == "skip"

    def test_exclude_without_include(self):
        ff = FileFilter({"exclude_patterns": ["*.tmp"]})
        assert ff.classify("video.mp4") == "process"
        assert ff.classify("video.tmp") == "skip"

    def test_passthrough_match(self):
        ff = FileFilter({"passthrough_patterns": ["*.txt", "*.srt"]})
        assert ff.classify("notes.txt") == "passthrough"
        assert ff.classify("sub/movie.srt") == "passthrough"
        assert ff.classify("video.mp4") == "process"

    def test_pipeline_include_exclude_passthrough(self):
        ff = FileFilter(
            {
                "include_patterns": ["alpha/*"],
                "exclude_patterns": ["*.tmp"],
                "passthrough_patterns": ["*.txt"],
            }
        )
        assert ff.classify("alpha/video.mp4") == "process"
        assert ff.classify("alpha/notes.txt") == "passthrough"
        assert ff.classify("alpha/cache.tmp") == "skip"
        assert ff.classify("beta/notes.txt") == "skip"

    def test_exclude_takes_priority_over_passthrough(self):
        ff = FileFilter(
            {"exclude_patterns": ["*.txt"], "passthrough_patterns": ["*.txt"]}
        )
        assert ff.classify("notes.txt") == "skip"

    def test_case_insensitive(self):
        ff = FileFilter({"include_patterns": ["*.MP4", "Alpha/*"]})
        assert ff.classify("video.mp4") == "process"
        assert ff.classify("VIDEO.MP4") == "process"
        assert ff.classify("ALPHA/video.mkv") == "process"

    def test_backslash_separator_normalized(self):
        ff = FileFilter({"include_patterns": ["alpha/*"]})
        assert ff.classify("alpha\\sub\\video.mp4") == "process"


class TestFileFilterCheckMtime:
    def test_threshold_zero_always_true(self):
        ff = FileFilter({"file_mtime": 0})
        assert ff.check_mtime(1000000, 2000000) is True

    def test_old_enough_file_passes(self):
        ff = FileFilter({"file_mtime": 300})
        assert ff.check_mtime(1000, 1400) is True

    def test_too_recent_file_fails(self):
        ff = FileFilter({"file_mtime": 300})
        assert ff.check_mtime(1000, 1100) is False

    def test_exact_threshold_passes(self):
        ff = FileFilter({"file_mtime": 300})
        assert ff.check_mtime(1000, 1300) is True
