import subprocess as sp
import os
import os.path as op
import sys
import shutil
from typing import Optional, List, Tuple

import pysrt
from timeit import default_timer as timer
import time
import easygui as g
import json
import tempfile
import re


class MediaError(Exception):
    pass


class SubtitleError(Exception):
    pass


ffmpeg_cmd: str = "utils/ffmpeg/ffmpeg"
ffprobe_cmd: str = "utils/ffmpeg/ffprobe"
video_exts: List[str] = [
    ".mkv",
    ".mp4",
    ".webm",
    ".mpg",
    ".mp2",
    ".mpeg",
    ".mpe",
    ".mpv",
    ".ogg",
    ".m4p",
    ".m4v",
    ".avi",
    ".wmv",
    ".mov",
    ".qt",
    ".flv",
    ".swf",
    ".mp3",
    ".wav",
    ".flac",
    ".m4a",
    ".aac",
]
sub_exts: List[str] = ["*.srt", "*.ass", "*.ssa", "*.vtt", "Subtitle files"]
title: str = "Condenser"
filtered_chars: str = ""
filter_parentheses: bool = False
output_format: str = ""
sub_suffix: str = ""
fixed_output_dir: Optional[str] = None
fixed_output_dir_with_subfolders: bool = True
output_condensed_subtitles: bool = False
padding: int = 500
mulsrt_ask: bool = False


def check_all_equal(li: List) -> bool:
    return li.count(li[0]) == len(li)


def probe_video(filename: str) -> Tuple[List[dict], List[dict]]:
    result = sp.run(
        [ffprobe_cmd, "-show_streams", "-v", "quiet", "-print_format", "json", filename], capture_output=True
    )
    if result.returncode != 0:
        raise ValueError("Could not probe video " + filename + " with ffprobe: " + str(result.stderr))
    probe = json.loads(result.stdout)
    streams = probe.get("streams")
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
    return audio_streams, subtitle_streams


def streams_to_options(streams: List[dict]) -> List[str]:
    options = ["(No tag)"] * len(streams)
    for i, a in enumerate(streams):
        if "tags" in a:
            s_lang = ""
            s_title = ""
            if "language" in a.get("tags"):
                s_lang = a.get("tags").get("language")
            if "title" in a.get("tags"):
                s_title = a.get("tags").get("title")
            if s_lang or s_title:
                options[i] = "{}: {} ({})".format(i + 1, s_title, s_lang)
    return options


def filter_text(text: str) -> str:
    text = re.sub("<[^<]+?>", "", text)  # strip xml tags
    if len(text) == 0:
        return ""

    if filter_parentheses and (
        (text[0] == "(" and text[-1] == ")")
        or (text[0] == "（" and text[-1] == "）")
        or (text[0] == "[" and text[-1] == "]")
        or (text[0] == "{" and text[-1] == "}")
    ):
        return ""

    if filtered_chars:
        return text.translate(str.maketrans("", "", filtered_chars))

    return text


def extract_periods(srt_path: str) -> List[List[int]]:
    subs = pysrt.open(srt_path)
    if not subs:
        raise SubtitleError("Could not open the subtitle file: " + srt_path)
    if filtered_chars or filter_parentheses:
        for sub in subs:
            sub.text = filter_text(sub.text)
    periods = [[sub.start.ordinal - padding, sub.end.ordinal + padding] for sub in subs if len(sub.text) > 0]

    if periods[0][0] < 0:
        periods[0][0] = 0
    periods[-1][1] -= padding

    merged_periods = []
    i = 0
    while i < len(periods):
        expanded = 0
        for j in range(i + 1, len(periods)):
            # if periods[i][1] + padding >= periods[j][0]:  # has extra padding
            if periods[i][1] >= periods[j][0]:
                periods[i][1] = periods[j][1]
                expanded += 1
            else:
                break
        merged_periods.append(periods[i])
        i += expanded + 1

    print("All period count: {} ({} filtered)".format(len(periods), len(subs) - len(periods)))
    print("Merged period count:", len(merged_periods))
    return merged_periods


def extract_audio_parts(periods: List[List[int]], temp_dir: str, filename: str, audio_index: int) -> List[str]:
    print("Extracting...")
    out_paths = []
    for i, (start, end) in enumerate(periods):
        out_path = temp_dir + "/out_{}.flac".format(i)
        out_paths.append(out_path)
        command = [
            ffmpeg_cmd,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            str(start / 1000),
            "-i",
            filename,
            "-t",
            str((end - start) / 1000),
            "-map",
            "0:a:{}".format(audio_index),
            "-c:a",
            "flac",
            "-compression_level",
            "0",
            out_path,
        ]
        rc = sp.call(command, shell=False)
        if rc != 0:
            raise MediaError("Could not extract audio from video")

        print("{}/{}".format(i + 1, len(periods)), end="\r")
    return out_paths


def concatenate_audio_parts(periods: List[List[int]], temp_dir: str, out_paths: List[str], output_filename: str):
    concat_dir = op.join(temp_dir, "concat.txt")
    with open(concat_dir, "w") as f:
        for i in range(len(periods)):
            f.write("file '{}'\n".format(out_paths[i].replace("'", "'\\''")))

    print("Concatenating...")
    concat_commands = [
        ffmpeg_cmd,
        "-y",
        "-safe",
        "0",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-i",
        concat_dir,
        output_filename,
    ]
    result = sp.run(concat_commands, capture_output=True)
    if result.returncode != 0:
        raise MediaError("There was a problem during concatenation: " + str(result.stderr))


def choose_audio_stream(audio_streams: List[dict], message: str) -> int:
    audio_index = 0
    if len(audio_streams) > 1:
        audio_options = streams_to_options(audio_streams)
        audio_index = g.indexbox(
            message, "Audio Stream", audio_options, default_choice=audio_options[audio_index], cancel_choice="cancel"
        )
        if audio_index is None:
            raise ValueError("Audio stream selection canceled. Exiting program.")
    return audio_index


def choose_subtitle_stream(subtitle_streams: List[dict], file_name_str: str = "this file") -> int:
    sub_index = 0
    if len(subtitle_streams) > 1 and mulsrt_ask:
        sub_options = streams_to_options(subtitle_streams)
        sub_index = g.indexbox(
            "No external and multiple internal subtitles found in {}. Which one would you like to use?".format(
                file_name_str
            )
            + " If you want to always pick the first subtitle by default,"
            ' set "ask_when_multiple_srt" to False in config.json',
            "Subtitle Stream",
            sub_options,
            default_choice=sub_options[sub_index],
            cancel_choice=sub_options[sub_index],
        )
    return sub_index


def extract_srt(temp_dir: str, filename: str, sub_index: int) -> str:
    srt_path = op.join(temp_dir, "out.srt")
    result = sp.run(
        [
            ffmpeg_cmd,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            filename,
            "-map",
            "0:s:{}".format(sub_index),
            srt_path,
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        raise MediaError("Could not extract subtitle with ffmpeg: " + str(result.stderr))
    return srt_path


def find_subtitle_with_same_name_as_file(filename: str) -> Optional[str]:
    file_root, _ = op.splitext(filename)
    for e in sub_exts[:-1]:
        path = file_root + sub_suffix + e[1:]
        if op.isfile(path):
            return path
    return None


def find_matching_subtitles_for_files(filenames: List[str]) -> Tuple[List[str], List[str]]:
    all_subtitle_paths = []
    invalid_videos = []
    for filename in filenames:
        subtitle = find_subtitle_with_same_name_as_file(filename)
        if subtitle:
            all_subtitle_paths.append(subtitle)
        else:
            invalid_videos.append(filename)
    return all_subtitle_paths, invalid_videos


def get_srt(subtitle_streams: List[dict], file_folder: str, filename: str, temp_dir: str) -> str:
    sub_path = find_subtitle_with_same_name_as_file(filename)

    if sub_path is None:
        # No same-name subs

        if len(subtitle_streams) >= 1:
            # Video has subtitles
            sub_index = choose_subtitle_stream(subtitle_streams)
            srt_path = extract_srt(temp_dir, filename, sub_index)
            return srt_path
        else:
            # No subs in video either, asking the user
            sub_path = g.fileopenbox(
                "This video file has no subtitles. Select a subtitle file to continue",
                title,
                filetypes=[sub_exts],
                default="{}/*".format(file_folder),
            )
            if sub_path is None:
                raise ValueError("Video file has no subtitles and subtitle file not selected. Exiting program.")

    return convert_sub_if_needed(sub_path, temp_dir)


def convert_sub_if_needed(sub_path: str, temp_dir: str) -> str:
    sub_root, sub_ext = op.splitext(sub_path)
    if sub_ext.lower() != ".srt":
        srt_path = op.join(temp_dir, "out.srt")
        sub_convert_cmd = [ffmpeg_cmd, "-i", sub_path, srt_path]
        result = sp.run(sub_convert_cmd, capture_output=True)
        if result.returncode != 0:
            raise SubtitleError("Could not open subtitle file " + sub_path + ": " + str(result.stderr))
    else:
        srt_path = sub_path
    return srt_path


def condense(srt_path: str, temp_dir: str, filename: str, audio_index: int, output_filename: str):
    time_start = timer()

    periods = extract_periods(srt_path)
    out_paths = extract_audio_parts(periods, temp_dir, filename, audio_index)
    concatenate_audio_parts(periods, temp_dir, out_paths, output_filename)

    if output_condensed_subtitles:
        condensed_srt_path = op.splitext(output_filename)[0] + ".srt"
        condense_subtitles(periods, srt_path, condensed_srt_path)

    time_end = timer()
    print("Finished in {:.2f} seconds".format(time_end - time_start))


def condense_subtitles(periods: List[List[int]], original_srt_path: str, condensed_srt_path: str):
    subs = pysrt.open(original_srt_path)
    condensed_subs = pysrt.SubRipFile()
    offset = 0  # Initialize an offset to track the condensed time

    for start, end in periods:
        end_time = end - start - offset
        for sub in subs:
            sub_start = sub.start.ordinal
            sub_end = sub.end.ordinal
            if sub_start >= start and sub_end <= end:
                # Adjust the subtitle's start and end times
                sub.start = pysrt.srttime.SubRipTime(milliseconds=sub_start - start + offset)
                sub.end = pysrt.srttime.SubRipTime(milliseconds=sub_end - start + offset)
                condensed_subs.append(sub)
        offset += end_time  # Update the offset based on the condensed timeline

    condensed_subs.save(condensed_srt_path, encoding="utf-8")


def condense_multi(
    subtitle_option: List[str],
    video_paths: List[str],
    video_names: List[str],
    subtitle_stream: List[dict],
    audio_stream: List[dict],
    parent_folder: str,
    folder_name: str,
    temp_dir: str,
):
    all_subtitle_paths, invalid_videos = find_matching_subtitles_for_files(video_paths)
    sub_index = 0
    if invalid_videos:
        # There is at least one video with no external sub
        if len(subtitle_option) == 0:
            # There are no internal subs
            raise ValueError(
                "There are videos with no subtitles and no corresponding subtitle files:\n" + "\n".join(invalid_videos)
            )
        is_all_none = all(s is None for s in all_subtitle_paths)
        file_name_str = "all files" if is_all_none else "some files"
        sub_index = choose_subtitle_stream(subtitle_stream, file_name_str)

    message = "These files have multiple audio streams. Which one would you like to use?"
    audio_index = choose_audio_stream(audio_stream, message)

    if fixed_output_dir is not None:
        if fixed_output_dir_with_subfolders:
            # Create sub-folder within fixed_output_dir
            output_dir: str = op.join(fixed_output_dir, folder_name + "_con")
        else:
            # Output directly to fixed_output_dir
            output_dir: str = fixed_output_dir
    else:
        output_dir: str = op.join(parent_folder, folder_name + "_con")
    os.makedirs(output_dir, exist_ok=True)
    all_time_start = timer()

    for i in range(len(video_paths)):
        v_path = video_paths[i]
        v_root = op.splitext(video_names[i])[0]
        output_filename = v_root + "." + output_format
        output_filepath = op.join(output_dir, output_filename)
        if op.isfile(output_filepath):
            print("{} already exists. Skipping".format(output_filename))
            continue

        print("Condensing video " + str(i + 1))
        os.makedirs(temp_dir, exist_ok=True)
        if all_subtitle_paths and all_subtitle_paths[i]:
            srt_path = convert_sub_if_needed(all_subtitle_paths[i], temp_dir)
        else:
            srt_path = extract_srt(temp_dir, v_path, sub_index)
        condense(srt_path, temp_dir, v_path, audio_index, output_filepath)

        shutil.rmtree(temp_dir, ignore_errors=True)

    all_time_end = timer()
    print("Finished {} files in {:.2f} seconds".format(len(video_paths), all_time_end - all_time_start))


def main(file_path: Optional[str] = None):
    temp_dir = None
    if getattr(sys, "frozen", False):
        application_path = op.dirname(op.abspath(sys.executable))
    else:
        application_path = op.dirname(op.abspath(__file__))

    try:
        # Load config
        config_path = op.join(application_path, "config.json")
        if op.isfile(config_path):
            with open(config_path, "r", encoding="utf8") as f:
                conf = json.load(f)
                if "padding" in conf:
                    global padding
                    padding = conf.get("padding")
                    if padding < 0:
                        padding = 0
                    if padding > 60000:
                        padding = 60000
                if "ask_when_multiple_srt" in conf:
                    global mulsrt_ask
                    mulsrt_ask = conf.get("ask_when_multiple_srt")
                if "filtered_characters" in conf:
                    global filtered_chars
                    filtered_chars = conf.get("filtered_characters")
                if "filter_parentheses" in conf:
                    global filter_parentheses
                    filter_parentheses = conf.get("filter_parentheses")
                if "output_format" in conf:
                    global output_format
                    output_format = conf.get("output_format")
                if "sub_suffix" in conf:
                    global sub_suffix
                    sub_suffix = conf.get("sub_suffix")
                if "fixed_output_dir" in conf:
                    global fixed_output_dir
                    fixed_output_dir = conf.get("fixed_output_dir")
                if "fixed_output_dir_with_subfolders" in conf:
                    global fixed_output_dir_with_subfolders
                    fixed_output_dir_with_subfolders = conf.get("fixed_output_dir_with_subfolders")
                if "use_system_ffmpeg" in conf:
                    global ffmpeg_cmd
                    global ffprobe_cmd
                    if conf.get("use_system_ffmpeg"):
                        ffmpeg_cmd = "ffmpeg"
                        ffprobe_cmd = "ffprobe"
                    else:
                        try:
                            sp.call([ffmpeg_cmd], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
                            sp.call([ffprobe_cmd], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
                        except FileNotFoundError:
                            print("ffmpeg or ffprobe not found in the utils/ffmpeg folder. Will try system ffmpeg")
                            ffmpeg_cmd = "ffmpeg"
                            ffprobe_cmd = "ffprobe"
                if "output_condensed_subtitles" in conf:
                    global output_condensed_subtitles
                    output_condensed_subtitles = conf.get("output_condensed_subtitles")

        # Get video file
        if file_path is None:
            msg = (
                "Would you like to condense one video or a folder of videos?\n"
                + "(You can also drag and drop videos or folders directly to the executable or its shortcut)"
            )
            answer = g.buttonbox(msg, title, ["Video", "Folder"])
            if answer == "Video":
                file_path = g.fileopenbox(
                    "Select video file", title, filetypes=[["*" + e for e in video_exts] + ["Video files"]]
                )
            elif answer == "Folder":
                file_path = g.diropenbox("Select folder", title)

        if file_path is None:
            raise ValueError("No input given")
        if not op.exists(file_path):
            raise OSError("No such file or directory: " + file_path)

        if op.isdir(file_path):
            print("Checking videos in folder:", file_path)

            parent_folder, folder_name = op.split(file_path)
            temp_dir = op.join(tempfile.gettempdir(), "condenser_temp-{}".format(int(time.time() * 1000)))

            file_names = [f for f in os.listdir(file_path) if op.isfile(op.join(file_path, f))]
            video_names = [f for f in file_names if op.splitext(f)[1] in video_exts]

            print("Found {} videos out of {} files".format(len(video_names), len(file_names)))
            video_paths = [op.join(file_path, f) for f in video_names]
            all_streams = [probe_video(v) for v in video_paths]
            all_audio_streams, all_subtitle_streams = map(list, zip(*all_streams, strict=True))
            all_audio_options = list(map(streams_to_options, all_audio_streams))
            all_subtitle_options = list(map(streams_to_options, all_subtitle_streams))
            if check_all_equal(all_audio_options) and check_all_equal(all_subtitle_options):
                print("Streams are consistent")
                condense_multi(
                    all_subtitle_options[0],
                    video_paths,
                    video_names,
                    all_subtitle_streams[0],
                    all_audio_streams[0],
                    parent_folder,
                    folder_name,
                    temp_dir,
                )
            else:
                all_options = list(zip(all_audio_options, all_subtitle_options, strict=True))
                grouped_options = [[(0, all_options[0])]]
                for i, o in enumerate(all_options[1:]):
                    found = False
                    for go in grouped_options:
                        if go[0][1] == o:
                            go.append((i + 1, o))
                            found = True
                            break
                    if not found:
                        grouped_options.append([(i + 1, o)])

                for go in grouped_options:
                    ids = [i for i, o in go]
                    so = go[0][1][1]
                    vps = [video_paths[i] for i in ids]
                    vns = [video_names[i] for i in ids]
                    s_s = all_subtitle_streams[ids[0]]
                    a_s = all_audio_streams[ids[0]]
                    condense_multi(so, vps, vns, s_s, a_s, parent_folder, folder_name, temp_dir)
        else:
            print("Opening video:", file_path)

            file_root, _ = op.splitext(file_path)
            file_folder, file_name = op.split(file_path)
            temp_dir = op.join(tempfile.gettempdir(), ".temp-{}".format(int(time.time() * 1000)))

            audio_streams, subtitle_streams = probe_video(file_path)
            os.makedirs(temp_dir)
            srt_path = get_srt(subtitle_streams, file_folder, file_path, temp_dir)
            audio_index = choose_audio_stream(
                audio_streams, "This file has multiple audio streams. Which one would you like to use?"
            )

            if fixed_output_dir is not None:
                os.makedirs(fixed_output_dir, exist_ok=True)
                file_name_root, _ = op.splitext(file_name)
                file_root = op.join(fixed_output_dir, file_name_root)
            condense(srt_path, temp_dir, file_path, audio_index, file_root + "_con." + output_format)

    except Exception as ex:
        print("{}: {}".format(type(ex).__name__, ex))
        import traceback

        print(traceback.format_exc())
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        heading = f"{time_str} - {file_path}"
        message = f"{heading}\n{'-' * len(heading)}\n{ex}\n{traceback.format_exc()}\n\n"
        with open(op.join(application_path, "log.txt"), "a") as f:
            f.write(message)

    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        main()
    else:
        main(sys.argv[1])
