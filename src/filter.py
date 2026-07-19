import fnmatch

import humanfriendly


def parse_size(val):
    if not val:
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    return humanfriendly.parse_size(str(val))


def parse_timespan(val):
    if not val:
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return humanfriendly.parse_timespan(str(val))
    except Exception:
        return float(val)


def parse_bitrate(val):
    if not val:
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip().upper()
    try:
        if val_str.endswith("KBPS") or val_str.endswith("K"):
            return float(val_str.replace("KBPS", "").replace("K", "").strip()) * 1024
        elif val_str.endswith("MBPS") or val_str.endswith("M"):
            return (
                float(val_str.replace("MBPS", "").replace("M", "").strip())
                * 1024
                * 1024
            )
        elif val_str.endswith("BPS"):
            return float(val_str.replace("BPS", "").strip())
    except ValueError:
        pass

    # fallback like size
    try:
        return humanfriendly.parse_size(val_str)
    except Exception:
        return float(val)


class FileFilter:
    def __init__(self, filter_config):
        self.config = filter_config

        self.include_patterns = [
            p.lower() for p in self.config.get("include_patterns", [])
        ]
        self.exclude_patterns = [
            p.lower() for p in self.config.get("exclude_patterns", [])
        ]
        self.passthrough_patterns = [
            p.lower() for p in self.config.get("passthrough_patterns", [])
        ]
        self.file_mtime = int(self.config.get("file_mtime", 0))

        self.size_min = parse_size(self._get_range("size", "min"))
        self.size_max = parse_size(self._get_range("size", "max"))

        self.duration_min = parse_timespan(self._get_range("duration", "min"))
        self.duration_max = parse_timespan(self._get_range("duration", "max"))

        self.v_bitrate_min = parse_bitrate(self._get_range("video_bitrate", "min"))
        self.v_bitrate_max = parse_bitrate(self._get_range("video_bitrate", "max"))

        self.a_bitrate_min = parse_bitrate(self._get_range("audio_bitrate", "min"))
        self.a_bitrate_max = parse_bitrate(self._get_range("audio_bitrate", "max"))

        self.t_bitrate_min = parse_bitrate(self._get_range("total_bitrate", "min"))
        self.t_bitrate_max = parse_bitrate(self._get_range("total_bitrate", "max"))

        self.framerate_min = float(self._get_range("framerate", "min") or 0)
        self.framerate_max = float(self._get_range("framerate", "max") or 0)

        self.short_side_min = int(self._get_range("short_side", "min") or 0)
        self.short_side_max = int(self._get_range("short_side", "max") or 0)

        self.exclude_vcodecs = [
            c.lower() for c in self.config.get("exclude_video_codecs", [])
        ]
        self.exclude_acodecs = [
            c.lower() for c in self.config.get("exclude_audio_codecs", [])
        ]

    def _get_range(self, key, boundary):
        val = self.config.get(key, {})
        if isinstance(val, dict):
            return val.get(boundary, 0)
        return 0

    @staticmethod
    def _match_patterns(rel_path, patterns):
        return any(fnmatch.fnmatchcase(rel_path, p) for p in patterns)

    def classify(self, rel_path):
        """
        根据相对路径判断文件分类（不区分大小写，路径分隔符统一为 '/'）。
        流水线: include -> exclude -> passthrough。
        返回 'skip'（跳过）、'passthrough'（直接移动）或 'process'（需要处理）。
        """
        rel_path = rel_path.replace("\\", "/").lower()

        if self.include_patterns and not self._match_patterns(
            rel_path, self.include_patterns
        ):
            return "skip"
        if self._match_patterns(rel_path, self.exclude_patterns):
            return "skip"
        if self._match_patterns(rel_path, self.passthrough_patterns):
            return "passthrough"
        return "process"

    def check_mtime(self, mtime, current_time):
        """
        检查文件修改时间是否满足阈值条件。
        mtime: 文件的实际修改时间戳
        current_time: 当前时间戳
        返回 True 表示通过（文件已稳定），False 表示应跳过。
        """
        if self.file_mtime <= 0:
            return True
        return (current_time - mtime) >= self.file_mtime
    
    def requires_media_info(self):
        """
        判断是否配置了需要 ffprobe 才能获取到的条件（即 size 和 mtime 以外的条件）
        如果只需要 size，就不用调用 ffprobe。
        """
        return any(
            [
                self.duration_min > 0,
                self.duration_max > 0,
                self.t_bitrate_min > 0,
                self.t_bitrate_max > 0,
                self.v_bitrate_min > 0,
                self.v_bitrate_max > 0,
                self.a_bitrate_min > 0,
                self.a_bitrate_max > 0,
                self.framerate_min > 0,
                self.framerate_max > 0,
                self.short_side_min > 0,
                self.short_side_max > 0,
                self.exclude_vcodecs,
                self.exclude_acodecs,
            ]
        )
    
    def match(self, media_info, logger=None, rel_path="", task_name=""):
        if self.size_min > 0 and media_info["size"] < self.size_min:
            if logger:
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 文件大小 ({media_info['size']}) 小于最小值 ({self.size_min})"
                )
            return False
        if self.size_max > 0 and media_info["size"] > self.size_max:
            if logger:
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 文件大小 ({media_info['size']}) 大于最大值 ({self.size_max})"
                )
            return False

        if self.duration_min > 0 and media_info["duration"] < self.duration_min:
            if logger:
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 时长 ({media_info['duration']}s) 小于最小值 ({self.duration_min}s)"
                )
            return False
        if self.duration_max > 0 and media_info["duration"] > self.duration_max:
            if logger:
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 时长 ({media_info['duration']}s) 大于最大值 ({self.duration_max}s)"
                )
            return False

        if self.t_bitrate_min > 0 and media_info["total_bitrate"] < self.t_bitrate_min:
            if logger:
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 总码率 ({media_info['total_bitrate']}) 小于最小值 ({self.t_bitrate_min})"
                )
            return False
        if self.t_bitrate_max > 0 and media_info["total_bitrate"] > self.t_bitrate_max:
            if logger:
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 总码率 ({media_info['total_bitrate']}) 大于最大值 ({self.t_bitrate_max})"
                )
            return False

        if self.v_bitrate_min > 0 and media_info["video_bitrate"] < self.v_bitrate_min:
            if logger:
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 视频码率 ({media_info['video_bitrate']}) 小于最小值 ({self.v_bitrate_min})"
                )
            return False
        if self.v_bitrate_max > 0 and media_info["video_bitrate"] > self.v_bitrate_max:
            if logger:
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 视频码率 ({media_info['video_bitrate']}) 大于最大值 ({self.v_bitrate_max})"
                )
            return False

        if self.a_bitrate_min > 0 and media_info["audio_bitrate"] < self.a_bitrate_min:
            if logger:
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 音频码率 ({media_info['audio_bitrate']}) 小于最小值 ({self.a_bitrate_min})"
                )
            return False
        if self.a_bitrate_max > 0 and media_info["audio_bitrate"] > self.a_bitrate_max:
            if logger:
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 音频码率 ({media_info['audio_bitrate']}) 大于最大值 ({self.a_bitrate_max})"
                )
            return False

        if self.framerate_min > 0 and media_info["framerate"] < self.framerate_min:
            if logger:
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 帧率 ({media_info['framerate']}) 小于最小值 ({self.framerate_min})"
                )
            return False
        if self.framerate_max > 0 and media_info["framerate"] > self.framerate_max:
            if logger:
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 帧率 ({media_info['framerate']}) 大于最大值 ({self.framerate_max})"
                )
            return False

        if self.short_side_min > 0 and media_info["short_side"] < self.short_side_min:
            if logger:
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 短边分辨率 ({media_info['short_side']}) 小于最小值 ({self.short_side_min})"
                )
            return False
        if self.short_side_max > 0 and media_info["short_side"] > self.short_side_max:
            if logger:
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 短边分辨率 ({media_info['short_side']}) 大于最大值 ({self.short_side_max})"
                )
            return False

        if (
            self.exclude_vcodecs
            and media_info["video_codec"].lower() in self.exclude_vcodecs
        ):
            if logger:
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 视频编码 ({media_info['video_codec']}) 在排除列表中 ({self.exclude_vcodecs})"
                )
            return False

        if (
            self.exclude_acodecs
            and media_info["audio_codec"].lower() in self.exclude_acodecs
        ):
            if logger:
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 音频编码 ({media_info['audio_codec']}) 在排除列表中 ({self.exclude_acodecs})"
                )
            return False

        return True
