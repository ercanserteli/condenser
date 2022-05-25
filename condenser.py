import subprocess as sp
import os
import os.path as op
import sys
import shutil
import pysrt
from timeit import default_timer as timer
import time
import easygui as g
import json
import tempfile
import re

ffmpeg_cmd = "utils\\ffmpeg\\ffmpeg"
ffprobe_cmd = "utils\\ffmpeg\\ffprobe"
video_exts = [".mkv", ".mp4", ".webm", ".mpg", ".mp2", ".mpeg", ".mpe", ".mpv", ".ogg", ".m4p",
              ".m4v", ".avi", ".wmv", ".mov", ".qt", ".flv", ".swf", ".mp3"]
sub_exts = ["*.srt", "*.ass", "*.ssa", "Subtitle files"]
title = "Condenser"
filtered_chars = ""
filter_parentheses = False


def check_all_equal(l):
    return l.count(l[0]) == len(l)


def probe_video(filename):
    result = sp.run(ffprobe_cmd + ' -show_streams -v quiet -print_format json "{}"'.format(filename),
                    capture_output=True)
    if result.returncode != 0:
        raise Exception("Could not probe video with ffprobe: " + str(result.stderr))
    probe = json.loads(result.stdout)
    streams = probe.get("streams")
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
    return audio_streams, subtitle_streams


def streams_to_options(streams):
    options = ["(No tag)"] * len(streams)
    for i, a in enumerate(streams):
        if "tags" in a:
            lang = ""
            title = ""
            if "language" in a.get("tags"):
                lang = a.get("tags").get("language")
            if "title" in a.get("tags"):
                title = a.get("tags").get("title")
            if lang or title:
                options[i] = "{}: {} ({})".format(i + 1, title, lang)
    return options


def filter_text(text):
    text = re.sub('<[^<]+?>', '', text)  # strip xml tags
    if len(text) == 0:
        return ""
    if filter_parentheses and \
            ((text[0] == "(" and text[-1] == ")") or \
             (text[0] == "[" and text[-1] == "]") or \
             (text[0] == "{" and text[-1] == "}")):
        return ""
    else:
        if filtered_chars:
            return text.translate(str.maketrans('', '', filtered_chars))
        else:
            return text


def extract_periods(srt_path, padding):
    subs = pysrt.open(srt_path)
    if not subs:
        raise Exception("Could not open the subtitle file: " + srt_path)
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
        i += (expanded + 1)

    print("All period count: {} ({} filtered)".format(len(periods), len(subs) - len(periods)))
    print("Merged period count:", len(merged_periods))
    return merged_periods


def extract_audio_parts(periods, temp_dir, filename, audio_index):
    print("Extracting...")
    out_paths = []
    for i, (start, end) in enumerate(periods):
        out_path = temp_dir + "\\out_{}.mp3".format(i)
        out_paths.append(out_path)
        command = ffmpeg_cmd + ' -hide_banner -loglevel error -ss {} -i "{}" -t {} -map 0:a:{} -q:a 4 "{}"'.format(
            start / 1000, filename, (end - start) / 1000, audio_index, out_path)
        rc = sp.call(command, shell=False)
        if rc != 0:
            raise Exception("Could not extract audio from video")

        print("{}/{}".format(i + 1, len(periods)), end="\r")
    return out_paths


def concatenate_audio_parts(periods, temp_dir, out_paths, output_filename):
    concat_dir = op.join(temp_dir, "concat.txt")
    with open(concat_dir, "w") as f:
        for i in range(len(periods)):
            f.write("file '{}'\n".format(out_paths[i].replace("'", "'\\''")))

    print("Concatenating...")
    concat_commands = [ffmpeg_cmd, "-y", "-safe", "0", "-hide_banner", "-loglevel", "error", "-f", "concat", "-i",
                       concat_dir, "-codec", "copy", output_filename]
    result = sp.run(concat_commands, capture_output=True)
    if result.returncode != 0:
        raise Exception("There was a problem during concatenation: " + str(result.stderr))


def choose_audio_stream(audio_streams, message):
    audio_index = 0
    if len(audio_streams) > 1:
        audio_options = streams_to_options(audio_streams)
        audio_index = g.indexbox(message, 'Audio Stream', audio_options, default_choice=audio_options[audio_index],
                                 cancel_choice=None)
        if audio_index is None:
            raise Exception("Audio stream selection canceled. Exiting program.")
    return audio_index


def choose_subtitle_stream(subtitle_streams, mulsrt_ask, file_name_str="this file"):
    sub_index = 0
    if len(subtitle_streams) > 1 and mulsrt_ask:
        sub_options = streams_to_options(subtitle_streams)
        sub_index = g.indexbox('No external and multiple internal subtitles found in {}. Which one would you like to use?'.format(file_name_str) +
                               ' If you want to always pick the first subtitle by default,'
                               ' set "ask_when_multiple_srt" to False in config.json',
                               'Subtitle Stream', sub_options, default_choice=sub_options[sub_index],
                               cancel_choice=sub_options[sub_index])
    return sub_index


def extract_srt(temp_dir, filename, sub_index):
    srt_path = op.join(temp_dir, "out.srt")
    result = sp.run(ffmpeg_cmd + ' -hide_banner -loglevel error -i "{}" -map 0:s:{} "{}"'.
                    format(filename, sub_index, srt_path), capture_output=True)
    if result.returncode != 0:
        raise Exception("Could not extract subtitle with ffmpeg: " + str(result.stderr))
    return srt_path


def find_same_name_sub(filename):
    # Checking if a subtitle file exists with the same name as the video file
    file_root, _ = op.splitext(filename)
    for e in sub_exts[:-1]:
        path = file_root + e[1:]
        if op.isfile(path):
            return path
    return None


def get_srt(subtitle_streams, mulsrt_ask, file_folder, filename, temp_dir):
    sub_path = find_same_name_sub(filename)

    if sub_path is None:
        # No same-name subs

        if len(subtitle_streams) >= 1:
            # Video has subtitles
            sub_index = choose_subtitle_stream(subtitle_streams, mulsrt_ask)
            srt_path = extract_srt(temp_dir, filename, sub_index)
            return srt_path
        else:
            # No subs in video either, asking the user
            sub_path = g.fileopenbox("This video file has no subtitles. Select a subtitle file to continue",
                                     title, filetypes=[sub_exts], default="{}\\*".format(file_folder))
            if sub_path is None:
                raise Exception("Video file has no subtitles and subtitle file not selected. Exiting program.")

    return convert_sub_if_needed(sub_path, temp_dir)

def convert_sub_if_needed(sub_path, temp_dir):
    sub_root, sub_ext = op.splitext(sub_path)
    if sub_ext.lower() != ".srt":
        srt_path = op.join(temp_dir, "out.srt")
        sub_convert_cmd = [ffmpeg_cmd, "-i", sub_path, srt_path]
        result = sp.run(sub_convert_cmd, capture_output=True)
        if result.returncode != 0:
            raise Exception("Could not open subtitle file " + sub_path + ": " + str(result.stderr))
    else:
        srt_path = sub_path
    return srt_path


def condense(srt_path, padding, temp_dir, filename, audio_index, output_filename):
    time_start = timer()

    periods = extract_periods(srt_path, padding)
    out_paths = extract_audio_parts(periods, temp_dir, filename, audio_index)
    concatenate_audio_parts(periods, temp_dir, out_paths, output_filename)

    time_end = timer()
    print("Finished in {:.2f} seconds".format(time_end - time_start))


def condense_multi(subtitle_option, video_paths, video_names, subtitle_stream, audio_stream, mulsrt_ask, parent_folder,
                   folder_name, temp_dir, padding):
    all_subtitle_paths = list(map(find_same_name_sub, video_paths))
    if None in all_subtitle_paths:
        # There is at least one video with no external sub
        if len(subtitle_option) == 0:
            # There are no internal subs
            raise Exception("There are videos with no subtitles and no corresponding subtitle files")
        is_all_none = all(s is None for s in all_subtitle_paths)
        file_name_str = "all files" if is_all_none else "some files"
        sub_index = choose_subtitle_stream(subtitle_stream, mulsrt_ask, file_name_str)

    message = 'These files have multiple audio streams. Which one would you like to use?'
    audio_index = choose_audio_stream(audio_stream, message)

    output_dir = op.join(parent_folder, folder_name + "_con")
    os.makedirs(output_dir, exist_ok=True)
    all_time_start = timer()

    for i in range(len(video_paths)):
        v_path = video_paths[i]
        v_root = op.splitext(video_names[i])[0]
        output_filename = v_root + ".mp3"
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
        condense(srt_path, padding, temp_dir, v_path, audio_index, output_filepath)

        shutil.rmtree(temp_dir, ignore_errors=True)

    all_time_end = timer()
    print("Finished {} files in {:.2f} seconds".format(len(video_paths), all_time_end - all_time_start))


def main():
    temp_dir = None
    filename = None
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(os.path.abspath(sys.executable))
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))

    try:
        # Load config
        config_path = op.join(application_path, "config.json")
        if op.isfile(config_path):
            with open(config_path, "r", encoding="utf8") as f:
                conf = json.load(f)
                padding = conf.get("padding")
                mulsrt_ask = conf.get("ask_when_multiple_srt")
                global filtered_chars; filtered_chars = conf.get("filtered_characters")
                global filter_parentheses; filter_parentheses = conf.get("filter_parentheses")
                if type(padding) is not int or type(mulsrt_ask) is not bool:
                    raise Exception("Invalid config file")
                if padding < 0:
                    padding = 0
                if padding > 60000:
                    padding = 60000
        else:
            padding = 500
            mulsrt_ask = False

        # Get video file
        if len(sys.argv) > 1:
            filename = sys.argv[1]
        else:
            answer = g.buttonbox("Would you like to condense one video or a folder of videos?\n"
                                 "(You can also drag and drop videos or folders directly to the executable or its shortcut)", title, ["Video", "Folder"])
            if answer == "Video":
                filename = g.fileopenbox("Select video file", title, filetypes=[["*" + e for e in video_exts] + ["Video files"]])
            elif answer == "Folder":
                filename = g.diropenbox("Select folder", title)

        if filename is None or not op.exists(filename):
            print("Filename is not given. Exiting")
            return

        if op.isdir(filename):
            print("Checking videos in folder:", filename)

            parent_folder, folder_name = op.split(filename)
            temp_dir = op.join(tempfile.gettempdir(), "condenser_temp-{}".format(int(time.time() * 1000)))

            file_names = [f for f in os.listdir(filename) if op.isfile(op.join(filename, f))]
            video_names = [f for f in file_names if op.splitext(f)[1] in video_exts]

            print("Found {} videos out of {} files".format(len(video_names), len(file_names)))
            video_paths = [op.join(filename, f) for f in video_names]
            all_streams = [probe_video(v) for v in video_paths]
            all_audio_streams, all_subtitle_streams = map(list, zip(*all_streams))
            all_audio_options = list(map(streams_to_options, all_audio_streams))
            all_subtitle_options = list(map(streams_to_options, all_subtitle_streams))
            if check_all_equal(all_audio_options) and check_all_equal(all_subtitle_options):
                print("Streams are consistent")
                condense_multi(all_subtitle_options[0], video_paths, video_names, all_subtitle_streams[0],
                               all_audio_streams[0], mulsrt_ask, parent_folder, folder_name, temp_dir, padding)
            else:
                all_options = list(zip(all_audio_options, all_subtitle_options))
                grouped_options = [[(0, all_options[0])]]
                for i, o in enumerate(all_options[1:]):
                    found = False
                    for go in grouped_options:
                        if go[0][1] == o:
                            go.append((i+1, o))
                            found = True
                            break
                    if not found:
                        grouped_options.append([(i+1, o)])

                for go in grouped_options:
                    ids = [i for i, o in go]
                    so = go[0][1][1]
                    vps = [video_paths[i] for i in ids]
                    vns = [video_names[i] for i in ids]
                    s_s = all_subtitle_streams[ids[0]]
                    a_s = all_audio_streams[ids[0]]
                    condense_multi(so, vps, vns, s_s, a_s, mulsrt_ask, parent_folder, folder_name, temp_dir, padding)
        else:
            print("Opening video:", filename)

            file_root, _ = os.path.splitext(filename)
            file_folder, _ = os.path.split(filename)
            temp_dir = op.join(tempfile.gettempdir(), ".temp-{}".format(int(time.time() * 1000)))

            audio_streams, subtitle_streams = probe_video(filename)
            os.makedirs(temp_dir)
            srt_path = get_srt(subtitle_streams, mulsrt_ask, file_folder, filename, temp_dir)
            audio_index = choose_audio_stream(audio_streams,
                                              'This file has multiple audio streams. Which one would you like to use?')

            condense(srt_path, padding, temp_dir, filename, audio_index, file_root + "_con.mp3")

    except Exception as ex:
        print("{}: {}".format(type(ex).__name__, ex))
        import traceback
        print(traceback.format_exc())
        with open(op.join(application_path, "log.txt"), "a") as f:
            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            heading = time_str + " - " + filename
            message = heading + "\n" + "-"*len(heading) + "\n" + str(ex) + "\nTraceback:\n" + traceback.format_exc() + "\n\n"
            f.write(message)
        # os.system("pause")

    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)
        # os.system("pause")


if __name__ == "__main__":
    main()
