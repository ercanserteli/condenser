Condenser by Ercan Serteli
--------------------------


What is this?
-------------
Condenser allows you to extract speech audio from video files, based on subtitle timings. This is mainly supposed to be used for passive immersion, where you are listening to the audio of something you have already watched. By omitting the audio outside of speech, it increases the language per second that you are getting exposed to. 


How to use - Simple
-------------------
* Unpack the archive to a folder and create a shortcut to condenser.exe if you want.
* Drag and drop a video or a folder with videos to the executable (or its shortcut).
* If there is an ambiguity, a pop up may ask you to make a choice. Answer accordingly.
* When the processing is done, an audio file with the name "[video_name]_con.mp3" will be created next to the video.


How to use - Detailed
---------------------
* Unpack the archive to a folder and create a shortcut to condenser.exe if you want.
* Single file:
    * Drag and drop a video to the executable (or its shortcut) or double click to run it and choose "Video" to select a file.
    * If the video has no embedded subtitles, it will look for a subtitle file of the same name in the same directory.
    * If it cannot find a suitable subtitle file either, it will ask you to select a subtitle file.
    * If there are multiple audio streams in the video file, it will ask you to pick one.
    * When the processing is done, an audio file with the name "[video_name]_con.mp3" will be created next to the video.
    * If an error occurs, the error message is written to a log.txt file in the executable directory.
* Folder:
    * Drag and drop a folder with videos to the executable (or its shortcut) or double click to run it and choose "Folder" to select a folder.
    * All of the video files in the folder must have the same group of audio and subtitle streams for this to work.
    * If the videos don't have embedded subtitles, it will look for a subtitle file of the same name for each video file.
    * If it cannot find suitable subtitle files either, the program will exit (it won't ask you to select a subtitle for every single video).
    * If there are multiple audio streams in the video files, it will ask you to pick one.
    * When the processing is done, a folder named "[folder_name]_con" will be created next to the input folder and mp3 files with the same name as the videos will be created within that folder.
    * If an error occurs, the error message is written to a log.txt file in the executable directory.

Config
------
You can change some settings in config.json:

"padding" is the amount of time that is added to the beginning and end of each subtitle period before extraction. The default is 500 ms and it works pretty well. Too short of a padding may slow down processing since the program merges overlapping periods before extracting audio. Also it may not give enough time to get context into what is happening in each line, making it less comprehensible.

"ask_when_multiple_srt" is False by default, which means it will pick the default (first) subtitle in a video file if it has multiple subtitles embedded. This is normally not a problem, but some videos may have strange subtitles put as the first one, such as "commentary" or "songs only". In this case, change this option to True and the program will ask which subtitle to use.


Project Webpage
---------------
Visit https://ercanserteli.com/condenser for further information and future updates


Acknowledgements
----------------
Condenser uses ffmpeg for manipulating video and audio files.