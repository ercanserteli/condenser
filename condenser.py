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


def main():
    ffmpeg_cmd = "utils\\ffmpeg\\ffmpeg"
    ffprobe_cmd = "utils\\ffmpeg\\ffprobe"
    temp_dir = None
    filename = ""
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
            filename = g.fileopenbox("Select video file", "Media Condenser", filetypes=[["*.mkv", "*.mp4", "Video files"]], default="*.mkv")

        if filename is None:
            print("Filename is not given. Exiting")
            return

        print("Opening video:", filename)

        file_root, _ = os.path.splitext(filename)
        file_folder, _ = os.path.split(filename)
        temp_dir = op.join(file_folder, ".temp-{}".format(int(time.time() * 1000)))

        # Probing video
        result = sp.run(ffprobe_cmd + ' -show_streams -v quiet -print_format json "{}"'.format(filename), capture_output=True)
        if result.returncode != 0:
            raise Exception("Could not probe video with ffprobe: " + result.stderr)
        probe = json.loads(result.stdout)
        streams = probe.get("streams")
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]

        srt_path = None
        # Getting subtitles
        if len(subtitle_streams) < 1:
            srt_path = g.fileopenbox("This video file has no subtitles! Select a SRT file", "Media Condenser",
                                     filetypes=["*.srt"], default="{}\\*.srt".format(file_folder))
            if srt_path is None:
                raise Exception("Video file has no subtitles and subtitle file not selected. Exiting program.")

        sub_index = 0
        if len(subtitle_streams) > 1 and mulsrt_ask:
            sub_options = ["(No tag)"] * len(subtitle_streams)
            for i, a in enumerate(subtitle_streams):
                if "tags" in a:
                    lang = ""
                    title = ""
                    if "language" in a.get("tags"):
                        lang = a.get("tags").get("language")
                    if "title" in a.get("tags"):
                        title = a.get("tags").get("title")
                    if lang or title:
                        sub_options[i] = "{}: {} ({})".format(i + 1, title, lang)

            sub_index = g.indexbox('This file has multiple subtitles. Which one would you like to use?'
                                   ' If you want to always pick the first subtitle by default,'
                                   ' set "ask_when_multiple_srt" to False in config.json',
                                   'Subtitle Stream', sub_options, default_choice=sub_options[sub_index],
                                   cancel_choice=sub_options[sub_index])

        # Choosing audio
        audio_index = 0
        if len(audio_streams) > 1:
            audio_options = ["(No tag)"] * len(audio_streams)
            for i, a in enumerate(audio_streams):
                if "tags" in a:
                    lang = ""
                    title = ""
                    if "language" in a.get("tags"):
                        lang = a.get("tags").get("language")
                        # audio_options[i] = "{}: {}".format(i + 1, lang)
                        if lang == "jpn":
                            audio_index = i
                    if "title" in a.get("tags"):
                        title = a.get("tags").get("title")
                    if lang or title:
                        audio_options[i] = "{}: {} ({})".format(i + 1, title, lang)

            audio_index = g.indexbox('This file has multiple audio streams. Which one would you like to use?',
                                     'Audio Stream', audio_options, default_choice=audio_options[audio_index],
                                     cancel_choice=None)
            if audio_index is None:
                raise Exception("Audio stream selection canceled. Exiting program.")

        time_start = timer()
        os.makedirs(temp_dir)

        # This means the video has subtitles
        if srt_path is None:
            srt_path = op.join(temp_dir, "out.srt")
            rc = sp.call(ffmpeg_cmd + ' -hide_banner -loglevel error -i "{}" -map 0:s:{} "{}"'.format(filename, sub_index, srt_path), shell=False)
            if rc != 0:
                raise Exception("Could not extract subtitle with ffmpeg")

        # Extracting and merging periods
        sub_filter = ["♬", "♬～"]
        subs = pysrt.open(srt_path)
        if not subs:
            raise Exception("Could not open the subtitle file: " + srt_path)
        periods = [[sub.start.ordinal - padding, sub.end.ordinal + padding] for sub in subs if sub.text not in sub_filter]

        if periods[0][0] < 0:
            periods[0][0] = 0
        periods[-1][1] -= padding

        new_periods = []
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
            new_periods.append(periods[i])
            i += (expanded + 1)

        print("All period count:", len(periods))
        print("Merged period count:", len(new_periods))

        # Extracting audio pieces
        print("Extracting...")
        out_paths = []
        for i, (start, end) in enumerate(new_periods):
            # out_path = temp_dir + "/out_{}.mkv".format(i)
            out_path = temp_dir + "\\out_{}.mp3".format(i)
            out_paths.append(out_path)
            # command = "ffmpeg -hide_banner -loglevel error -i {} -ss {} -t {} -codec copy {}".format(
            command = ffmpeg_cmd + ' -hide_banner -loglevel error -i "{}" -ss {} -t {} -map 0:a:{} -q:a 4 "{}"'.format(
                filename, start/1000, (end-start)/1000, audio_index, out_path)
            rc = sp.call(command, shell=False)
            if rc != 0:
                raise Exception("Could not extract audio from video")

            print("{}/{}".format(i+1, len(new_periods)), end="\r")

        # Concatenating audio pieces into one
        concat_dir = op.join(temp_dir, "concat.txt")
        with open(concat_dir, "w") as f:
            for i in range(len(new_periods)):
                f.write("file '{}'\n".format(out_paths[i].replace("'", "'\\''")))

        print("Concatenating...")
        output_filename = file_root + "_condensed.mp3"
        concat_commands = [ffmpeg_cmd, "-y", "-safe", "0", "-hide_banner", "-loglevel", "error", "-f", "concat", "-i", concat_dir, "-codec", "copy", output_filename]
        # concat_commands_str = ffmpeg_cmd + ' -y -safe 0 -hide_banner -loglevel error -f concat -i "{}" -codec copy "{}"'.format(concat_dir, output_filename)
        result = sp.run(concat_commands)
        if result.returncode != 0:
            raise Exception("There was a problem during concatenation: " + result.stderr)

        time_end = timer()
        print("Finished in", time_end - time_start, "seconds")

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
