import os
import shutil
import subprocess
import sys
import time

import humanfriendly

from src.utils import clean_empty_dirs, get_media_duration


def cleanup_expired_files(expired_files, db_manager, logger):
    for filepath in expired_files:
        try:
            os.remove(filepath)
            logger.info(f"已删除过期源文件: {filepath}")
            db_manager.delete_record(filepath)
        except OSError as e:
            logger.error(f"删除过期源文件失败: {filepath}\n{e}")


def process_file(entry, task_config, db_manager, logger):
    filepath = entry.filepath
    task_name = task_config.name
    source_dir = task_config.source_dir

    rel_path = os.path.relpath(filepath, source_dir)

    stable_duration = task_config.stable_duration
    if stable_duration > 0:
        try:
            old_size = os.path.getsize(filepath)
        except OSError:
            logger.warning(f"【{task_name}】文件 {rel_path} 已不存在，跳过处理。")
            logger.debug(
                f"【{task_name}】跳过 {rel_path}，原因: 执行稳定性检查时文件已不存在"
            )
            return

        logger.info(
            f"【{task_name}】正在检查 {rel_path} 在 {stable_duration} 秒内的一致性……"
        )
        logger.debug(f"【{task_name}】{rel_path} 稳定性检查前大小: {old_size} 字节")
        time.sleep(stable_duration)

        try:
            new_size = os.path.getsize(filepath)
            logger.debug(f"【{task_name}】{rel_path} 稳定性检查后大小: {new_size} 字节")
            if new_size != old_size:
                logger.info(f"【{task_name}】文件 {rel_path} 正在变化，跳过本次处理。")
                logger.debug(
                    f"【{task_name}】跳过 {rel_path}，原因: 文件大小从 {old_size} 变为 {new_size}，文件仍在变化中"
                )
                return
        except OSError:
            logger.warning(f"【{task_name}】文件 {rel_path} 已不存在，跳过处理。")
            logger.debug(
                f"【{task_name}】跳过 {rel_path}，原因: 稳定性检查后文件已不存在"
            )
            return
    else:
        if not os.path.exists(filepath):
            logger.warning(f"【{task_name}】文件 {rel_path} 已不存在，跳过处理。")
            return

    dest_dir = task_config.dest_dir
    remove_source = task_config.remove_source
    source_expired_minutes = task_config.source_expired_minutes
    backup_dir = task_config.backup_dir

    rel_dir = os.path.dirname(rel_path)
    final_dest_dir = os.path.join(dest_dir, rel_dir)
    filename = os.path.basename(filepath)
    name, _ext = os.path.splitext(filename)

    if entry.action == "passthrough":
        dst_filepath = os.path.join(final_dest_dir, filename)
        os.makedirs(final_dest_dir, exist_ok=True)

        try:
            logger.info(f"【{task_name}】直接移动文件 {rel_path} 至 {dest_dir}")
            shutil.move(filepath, dst_filepath)
            db_manager.mark_success(filepath, time.time())
            clean_empty_dirs(source_dir)
        except Exception as e:  # noqa: BLE001
            # 兜底捕获：单个文件的失败不允许中断监听循环，统一记入失败计数
            logger.error(f"【{task_name}】直接移动文件失败: {rel_path}\n{e}")
            db_manager.increment_failure(filepath)
        return

    # 构造输出文件基础路径（不含扩展名）
    dst_basepath = os.path.join(final_dest_dir, name)

    # 确保输出目录存在
    os.makedirs(final_dest_dir, exist_ok=True)

    # 记录处理前目标目录的文件列表，用于失败时清理不完整的输出文件
    existing_files = set(os.listdir(final_dest_dir))

    if entry.media_info and "duration" in entry.media_info:
        duration = humanfriendly.format_timespan(entry.media_info["duration"])
    else:
        logger.debug(f"【{task_name}】未预获取媒体时长，通过 ffprobe 获取: {rel_path}")
        duration = humanfriendly.format_timespan(get_media_duration(filepath))

    fallback_count = task_config.fallback_count
    ffmpeg_cmd_fallback = task_config.ffmpeg_cmd_fallback

    use_fallback = False
    if (
        fallback_count > 0
        and ffmpeg_cmd_fallback
        and db_manager.get_ffmpeg_failure_count(filepath) >= fallback_count
    ):
        use_fallback = True

    if use_fallback:
        raw_cmd = ffmpeg_cmd_fallback.format(input=filepath, output=dst_basepath)
        logger.info(
            f"【{task_name}】使用 fallback 命令处理 {rel_path}，媒体时长 {duration}。"
        )
    else:
        raw_cmd = task_config.ffmpeg_cmd.format(input=filepath, output=dst_basepath)
        logger.info(f"【{task_name}】开始处理 {rel_path}，媒体时长 {duration}。")

    # 将多行命令合并为单行，替换换行符为空格，以支持在配置文件中换行提高可读性
    cmd = raw_cmd.replace("\n", " ").replace("\r", " ")

    logger.debug(f"【{task_name}】执行 FFmpeg 命令: {cmd}")

    start_time = time.time()
    try:
        # 执行命令，使用 Popen 实时读取输出
        process = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        last_status_line = ""
        error_output = []
        final_status = ""
        last_print_time = 0
        is_tty = sys.stdout.isatty()

        # 实时读取 stderr
        while True:
            char = process.stderr.read(1)
            if not char and process.poll() is not None:
                break

            if char:
                # errors="ignore" 保证解码永远不会抛出异常
                c = char.decode("utf-8", errors="ignore")

                if c == "\r" or c == "\n":
                    line = last_status_line.strip()
                    if line:
                        error_output.append(line)
                        # 只打印包含进度信息的行
                        if "time=" in line or "speed=" in line:
                            current_time = time.time()
                            if is_tty:
                                # TTY 环境下使用 \r 覆盖当前行
                                print(f"\r{line.ljust(100)}", end="", flush=True)
                            else:
                                # 非 TTY 环境（如 Docker 默认日志），每 5 秒打印一次并换行，避免日志缓冲不显示和刷屏
                                if current_time - last_print_time >= 5.0:
                                    print(line, flush=True)
                                    last_print_time = current_time
                            final_status = line
                    last_status_line = ""
                else:
                    last_status_line += c

        # 确保最后一行也被处理
        line = last_status_line.strip()
        if line:
            error_output.append(line)
            if "time=" in line or "speed=" in line:
                if is_tty:
                    print(f"\r{line.ljust(100)}", end="", flush=True)
                else:
                    print(line, flush=True)
                final_status = line

        if final_status and is_tty:
            print()  # 换行，避免后续日志覆盖

        process.wait()
        elapsed_time = time.time() - start_time

        if process.returncode == 0:
            logger.info(
                f"【{task_name}】处理成功，输出至 {dest_dir}，耗时 {humanfriendly.format_timespan(elapsed_time)}。"
            )
            if final_status:
                logger.info(f"【{task_name}】FFmpeg 运行报告: {final_status}")

            if remove_source:
                if source_expired_minutes == 0:
                    try:
                        os.remove(filepath)
                        logger.info(f"【{task_name}】已删除源文件: {rel_path}")
                    except OSError as e:
                        logger.error(f"【{task_name}】删除源文件失败: {rel_path}\n{e}")
                    db_manager.mark_success(filepath, time.time())
                else:
                    db_manager.mark_success(filepath, time.time())
                    logger.info(
                        f"【{task_name}】源文件 {rel_path} 将在 {source_expired_minutes} 分钟后删除。"
                    )
            else:
                if backup_dir:
                    bak_dir = os.path.join(backup_dir, rel_dir)
                    bak_filepath = os.path.join(bak_dir, filename)
                    os.makedirs(bak_dir, exist_ok=True)

                    logger.debug(
                        f"【{task_name}】移动源文件到备份目录: {filepath} -> {bak_filepath}"
                    )
                    shutil.move(filepath, bak_filepath)
                else:
                    logger.info(f"【{task_name}】源文件保留在原位置: {rel_path}")

                db_manager.mark_success(filepath, time.time())

            # 清理 source_dir 中的空文件夹
            clean_empty_dirs(source_dir)
        else:
            error_msg = "\n".join(error_output[-20:])  # 只取最后20行错误信息
            logger.error(f"【{task_name}】处理失败，原因:\n{error_msg}")

            # 增加失败次数
            if use_fallback:
                db_manager.increment_failure(filepath)
            else:
                if fallback_count > 0 and ffmpeg_cmd_fallback:
                    db_manager.increment_ffmpeg_failure(filepath)
                else:
                    db_manager.increment_failure(filepath)

            # 如果生成了不完整的输出文件，将其删除
            if os.path.exists(final_dest_dir):
                current_files = set(os.listdir(final_dest_dir))
                new_files = current_files - existing_files
                for f in new_files:
                    if f.startswith(name):
                        f_path = os.path.join(final_dest_dir, f)
                        if os.path.exists(f_path):
                            try:
                                os.remove(f_path)
                            except OSError:
                                pass

    except Exception as e:  # noqa: BLE001
        # 兜底捕获：单个文件的失败不允许中断监听循环，统一记入失败计数
        logger.error(f"【{task_name}】其他失败，原因:\n{e}")
        db_manager.increment_failure(filepath)
