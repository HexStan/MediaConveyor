import json
import os
import subprocess


def get_media_info(filepath):
    """
    使用 ffprobe 获取多媒体文件详细信息
    返回格式:
    {
        "duration": 时长（秒）,
        "size": 文件大小（字节）,
        "total_bitrate": 总体码率（bps）,
        "video_bitrate": 视频流码率（bps）,
        "audio_bitrate": 音频流码率（bps）,
        "framerate": 视频帧率（fps）,
        "short_side": 视频短边像素（短边分辨率）,
        "video_codec": 视频编码格式,
        "audio_codec": 音频编码格式,
    }
    """
    # 默认结果
    info = {
        "duration": 0.0,
        "size": 0,
        "total_bitrate": 0,
        "video_bitrate": 0,
        "audio_bitrate": 0,
        "framerate": 0.0,
        "short_side": 0,
        "video_codec": "",
        "audio_codec": "",
    }

    try:
        # 获取文件大小
        if os.path.exists(filepath):
            info["size"] = os.path.getsize(filepath)
    except OSError:
        pass

    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        filepath,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15, check=False
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)

            fmt = data.get("format", {})
            if "duration" in fmt:
                try:
                    info["duration"] = float(fmt["duration"])
                except ValueError:
                    pass
            if "bit_rate" in fmt:
                try:
                    info["total_bitrate"] = float(fmt["bit_rate"])
                except ValueError:
                    pass

            for stream in data.get("streams", []):
                codec_type = stream.get("codec_type")
                if codec_type == "video" and not info["video_codec"]:
                    info["video_codec"] = stream.get("codec_name", "")
                    if "bit_rate" in stream:
                        try:
                            info["video_bitrate"] = float(stream["bit_rate"])
                        except ValueError:
                            pass

                    width = stream.get("width", 0)
                    height = stream.get("height", 0)
                    if width and height:
                        info["short_side"] = min(width, height)

                    # 尝试计算帧率，形如 "24000/1001" 或 "24/1"
                    fps_str = stream.get("avg_frame_rate") or stream.get(
                        "r_frame_rate", ""
                    )
                    if fps_str and "/" in fps_str:
                        num, den = fps_str.split("/")
                        try:
                            if float(den) != 0:
                                info["framerate"] = float(num) / float(den)
                        except ValueError:
                            pass
                elif codec_type == "audio" and not info["audio_codec"]:
                    info["audio_codec"] = stream.get("codec_name", "")
                    if "bit_rate" in stream:
                        try:
                            info["audio_bitrate"] = float(stream["bit_rate"])
                        except ValueError:
                            pass
    except Exception as e:  # noqa: BLE001
        # 兜底捕获：ffprobe 的任何异常（缺失、超时、输出异常）都不允许向上抛出，
        # 必须降级为全零默认值
        print(f"Error fetching media info with ffprobe: {e}")

    return info


def get_media_duration(filepath):
    """
    使用 ffprobe 获取音视频时长（秒），通过 get_media_info 获得。
    保留此函数为了兼容性。
    """
    return get_media_info(filepath).get("duration", 0.0)


def clean_empty_dirs(directory):
    """
    递归删除指定目录下的所有空文件夹
    """
    if not os.path.exists(directory):
        return

    # topdown=False 保证先处理子目录，再处理父目录
    for dirpath, dirnames, filenames in os.walk(directory, topdown=False):
        # 不要删除根目录本身
        if os.path.abspath(dirpath) == os.path.abspath(directory):
            continue

        # 如果目录为空（没有文件也没有子目录）
        if not os.listdir(dirpath):
            try:
                os.rmdir(dirpath)
            except OSError:
                pass
