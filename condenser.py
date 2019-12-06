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

ffmpeg_cmd = "utils\\ffmpeg\\ffmpeg"
ffprobe_cmd = "utils\\ffmpeg\\ffprobe"
video_exts = [".mkv", ".mp4", ".webm", ".mpg", ".mp2", ".mpeg", ".mpe", ".mpv", ".ogg", ".m4p", ".m4v", ".avi", ".wmv", ".mov", ".qt", ".flv", ".swf"]
sub_exts = ["*.srt", "*.ass", "*.ssa", "Subtitle files"]
title = "Condenser"


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


def extract_periods(srt_path, padding):
    sub_filter = ["♬", "♬～"]
    subs = pysrt.open(srt_path)
    if not subs:
        raise Exception("Could not open the subtitle file: " + srt_path)
    periods = [[sub.start.ordinal - padding, sub.end.ordinal + padding] for sub in subs if sub.text not in sub_filter]

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

    print("All period count:", len(periods))
    print("Merged period count:", len(merged_periods))
    return merged_periods


def extract_audio_parts(periods, temp_dir, filename, audio_index):
    print("Extracting...")
    out_paths = []
    for i, (start, end) in enumerate(periods):
        # out_path = temp_dir + "/out_{}.mkv".format(i)
        out_path = temp_dir + "\\out_{}.mp3".format(i)
        out_paths.append(out_path)
        # command = "ffmpeg -hide_banner -loglevel error -i {} -ss {} -t {} -codec copy {}".format(
        command = ffmpeg_cmd + ' -hide_banner -loglevel error -i "{}" -ss {} -t {} -map 0:a:{} -q:a 4 "{}"'.format(
            filename, start / 1000, (end - start) / 1000, audio_index, out_path)
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


def choose_subtitle_stream(subtitle_streams, mulsrt_ask):
    sub_index = 0
    if len(subtitle_streams) > 1 and mulsrt_ask:
        sub_options = streams_to_options(subtitle_streams)
        sub_index = g.indexbox('This file has multiple subtitles. Which one would you like to use?'
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
    if len(subtitle_streams) < 1:
        sub_path = find_same_name_sub(filename)

        if sub_path is None:
            # No same-name sub, asking the user
            sub_path = g.fileopenbox("This video file has no subtitles. Select a subtitle file to continue",
                                     title, filetypes=[sub_exts], default="{}\\*".format(file_folder))
            if sub_path is None:
                raise Exception("Video file has no subtitles and subtitle file not selected. Exiting program.")

        sub_root, sub_ext = op.splitext(sub_path)
        if sub_ext.lower() != ".srt":
            srt_path = op.join(temp_dir, "out.srt")
            sub_convert_cmd = ["ffmpeg", "-i", sub_path, srt_path]
            result = sp.run(sub_convert_cmd, capture_output=True)
            if result.returncode != 0:
                raise Exception("Could not open subtitle file " + sub_path + ": " + str(result.stderr))
        else:
            srt_path = sub_path
    else:
        # Video has subtitles
        sub_index = choose_subtitle_stream(subtitle_streams, mulsrt_ask)
        srt_path = extract_srt(temp_dir, filename, sub_index)
    return srt_path


def condense(srt_path, padding, temp_dir, filename, audio_index, output_filename):
    time_start = timer()

    periods = extract_periods(srt_path, padding)
    out_paths = extract_audio_parts(periods, temp_dir, filename, audio_index)
    concatenate_audio_parts(periods, temp_dir, out_paths, output_filename)

    time_end = timer()
    print("Finished in {:.2f} seconds".format(time_end - time_start))


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
            with open(config_path, "r") as f:
                conf = json.load(f)
                padding = conf.get("padding")
                mulsrt_ask = conf.get("ask_when_multiple_srt")
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
            answer = g.buttonbox("Would you like to condense one video or a folder of videos?", title, ["Video", "Folder"])
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
            temp_dir = op.join(parent_folder, "condenser_temp-{}".format(int(time.time() * 1000)))

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

                all_subtitle_paths = None
                if len(all_subtitle_options[0]) == 0:
                    all_subtitle_paths = list(map(find_same_name_sub, video_paths))
                    if None in all_subtitle_paths:
                        raise Exception("There are videos with no subtitles and no corresponding subtitle files")

                sub_index = choose_subtitle_stream(all_subtitle_streams[0], mulsrt_ask)
                message = 'These files have multiple audio streams. Which one would you like to use?'
                audio_index = choose_audio_stream(all_audio_streams[0], message)

                output_dir = op.join(parent_folder, folder_name + "_con")
                os.makedirs(output_dir)
                all_time_start = timer()

                for i in range(len(video_paths)):
                    print("Condensing video " + str(i+1))
                    os.makedirs(temp_dir)

                    v_path = video_paths[i]
                    v_root = op.splitext(video_names[i])[0]
                    if all_subtitle_paths:
                        srt_path = all_subtitle_paths[i]
                    else:
                        srt_path = extract_srt(temp_dir, v_path, sub_index)
                    condense(srt_path, padding, temp_dir, v_path, audio_index, op.join(output_dir, v_root + ".mp3"))

                    shutil.rmtree(temp_dir, ignore_errors=True)

                all_time_end = timer()
                print("Finished {} files in {:.2f} seconds".format(len(all_audio_streams), all_time_end - all_time_start))
            else:
                raise Exception("Videos in folder are not uniform")
        else:
            print("Opening video:", filename)

            file_root, _ = os.path.splitext(filename)
            file_folder, _ = os.path.split(filename)
            temp_dir = op.join(file_folder, ".temp-{}".format(int(time.time() * 1000)))

            audio_streams, subtitle_streams = probe_video(filename)
            os.makedirs(temp_dir)
            srt_path = get_srt(subtitle_streams, mulsrt_ask, file_folder, filename, temp_dir)
            audio_index = choose_audio_stream(audio_streams,
                                              'This file has multiple audio streams. Which one would you like to use?')

            condense(srt_path, padding, temp_dir, filename, audio_index, file_root + "_con.mp3")

    except Exception as ex:
        print(ex)
        with open(op.join(application_path, "log.txt"), "a") as f:
            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            heading = time_str + " - " + filename
            message = heading + "\n" + "-"*len(heading) + "\n" + str(ex) + "\n\n"
            f.write(message)
        # os.system("pause")

    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)
        # os.system("pause")


if __name__ == "__main__":
    main()
