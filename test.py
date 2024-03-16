import inspect
import json
import os
import os.path as op
import shutil
import unittest
from unittest.mock import patch

from condenser import main


def are_files_similar(file_path1, file_path2, tolerance_bytes=1024):
    """Different ffmpeg versions produce slightly different output files, so this checks the size with some tolerance"""
    return abs(op.getsize(file_path1) - op.getsize(file_path2)) <= tolerance_bytes


def caller_function_name():
    frame = inspect.currentframe().f_back.f_back
    # Ensure that there is such a frame
    if frame is not None:
        return frame.f_code.co_name


def config_set(key, val):
    print(f"Setting {key} to {val}")
    shutil.copy("config.json", "config.json.bak")
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    if isinstance(key, str):
        config[key] = val
    elif isinstance(key, tuple) and isinstance(val, tuple):
        for k, v in zip(key, val, strict=True):
            config[k] = v

    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def restore_config():
    if op.exists("config.json.bak"):
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        if config.get("fixed_output_dir") is not None:
            shutil.rmtree(config["fixed_output_dir"], ignore_errors=True)

        shutil.copy("config.json.bak", "config.json")
        os.remove("config.json.bak")


class TestFiles(unittest.TestCase):
    _input_dir = "test_files/inputs"
    _output_dir = "test_files/outputs"
    _delete_outputs = True

    def tearDown(self):
        restore_config()
        if self._delete_outputs:
            for filename in os.listdir(self._input_dir):
                if "_con." in filename:
                    os.remove(f"{self._input_dir}/{filename}")

    def _testFile(self, filename, output_formats=("mp3",), out_test_dir=None):
        print(caller_function_name())
        try:
            main(f"{self._input_dir}/{filename}")
        except Exception as e:
            self.fail(str(e))

        for output_format in output_formats:
            self._checkOutput(filename, output_format, out_test_dir)

    def _checkOutput(self, filename, output_format="mp3", out_test_dir=None):
        if out_test_dir is None:
            out_test_dir = self._input_dir
        filename_root = op.splitext(filename)[0]
        out_test_path = f"{out_test_dir}/{filename_root}_con.{output_format}"
        out_true_path = f"{self._output_dir}/{filename_root}_con.{output_format}"
        self.assertTrue(op.exists(out_test_path), f"Output file {out_test_path} does not exist")
        self.assertTrue(op.exists(out_true_path), f"Output file {out_true_path} does not exist")
        self.assertTrue(are_files_similar(out_test_path, out_true_path))

    def test1a1s(self):
        self._testFile("1a1s.mkv")

    @patch("easygui.indexbox")
    def test3a1s(self, mock_indexbox):
        mock_indexbox.return_value = 2
        self._testFile("3a1s.mkv")

    def test1a0s(self):
        self._testFile("1a0s.mkv")

    @patch("easygui.fileopenbox")
    def test1a0sGUIForSubtitles(self, mock_fileopenbox):
        sub_org_filepath = f"{self._input_dir}/1a0s"
        sub_temp_filepath = f"{self._input_dir}/1a0s_renamed"

        for ext in [".srt", ".ass", ".vtt"]:
            os.rename(sub_org_filepath + ext, sub_temp_filepath + ext)

        mock_fileopenbox.return_value = sub_temp_filepath + ".srt"
        self._testFile("1a0s.mkv")

        for ext in [".srt", ".ass", ".vtt"]:
            os.rename(sub_temp_filepath + ext, sub_org_filepath + ext)

    @patch("easygui.indexbox")
    def test3a2s(self, mock_indexbox):
        mock_indexbox.side_effect = [1, 2]
        self._testFile("3a2s.mkv")

    def testAudioInput(self):
        self._testFile("audio_1.mp3")

    def testFlacOutput(self):
        config_set("output_format", "flac")
        self._testFile("1a0s.mkv", ("flac",))

    def testFixedOutputDir(self):
        current_directory = os.getcwd()
        output_dir = op.join(current_directory, "test_out")
        config_set("fixed_output_dir", output_dir)
        self._testFile("1a0s.mkv", out_test_dir=output_dir)

    def testSubtitleOutput(self):
        config_set("output_condensed_subtitles", True)
        self._testFile("1a0s.mkv", ("mp3", "srt"))

    @patch("easygui.fileopenbox")
    @patch("easygui.buttonbox")
    def testWithGUISelection(self, mock_buttonbox, mock_fileopenbox):
        file_name = "1a0s.mkv"
        mock_buttonbox.return_value = "Video"
        mock_fileopenbox.return_value = f"{self._input_dir}/{file_name}"

        main()
        self._checkOutput(file_name)


class TestFolders(unittest.TestCase):
    _input_dir = "test_files/inputs"
    _output_dir = "test_files/outputs"
    _delete_outputs = True

    def tearDown(self):
        restore_config()
        if self._delete_outputs:
            for folder_name in os.listdir(self._input_dir):
                if folder_name.endswith("_con") and op.isdir(f"{self._input_dir}/{folder_name}"):
                    shutil.rmtree(f"{self._input_dir}/{folder_name}", ignore_errors=True)

        # Clean up temporary folders
        for folder_name in os.listdir(self._input_dir):
            if folder_name.endswith("_temp") and op.isdir(f"{self._input_dir}/{folder_name}"):
                shutil.rmtree(f"{self._input_dir}/{folder_name}", ignore_errors=True)
        for folder_name in os.listdir(self._output_dir):
            if folder_name.endswith("_temp") and op.isdir(f"{self._output_dir}/{folder_name}"):
                shutil.rmtree(f"{self._output_dir}/{folder_name}", ignore_errors=True)

    def _testFolder(self, folder_name, out_test_dir=None, subfolder=True):
        print(caller_function_name())
        try:
            main(f"{self._input_dir}/{folder_name}")
        except Exception as e:
            self.fail(str(e))

        self._checkOutput(folder_name, out_test_dir, subfolder)

    def _checkOutput(self, folder_name, out_test_dir=None, subfolder=True):
        # Compare hash of output files with the true output files
        if out_test_dir is None:
            out_test_dir = self._input_dir
        out_test_path = f"{out_test_dir}/{folder_name}_con" if subfolder else out_test_dir
        out_true_path = f"{self._output_dir}/{folder_name}"
        self.assertTrue(op.exists(out_test_path), f"Output folder {out_test_path} does not exist")
        self.assertTrue(op.exists(out_true_path), f"Output folder {out_true_path} does not exist")
        for filename in os.listdir(out_test_path):
            if op.isfile(f"{out_test_path}/{filename}"):
                file_base, file_ext = op.splitext(filename)
                out_filename = f"{file_base}_con{file_ext}"
                self.assertTrue(are_files_similar(f"{out_test_path}/{filename}", f"{out_true_path}/{out_filename}"))

    def _createTestFolder(self, folder_name: str, prefix_filters: tuple, with_copies: bool = True):
        def create(base_folder):
            folder_path = f"{base_folder}/{folder_name}_temp"
            os.makedirs(folder_path)
            for filename in os.listdir(f"{base_folder}"):
                if op.isfile(f"{base_folder}/{filename}") and filename.startswith(prefix_filters):
                    shutil.copy(f"{base_folder}/{filename}", f"{folder_path}/{filename}")
                    if with_copies:
                        shutil.copy(f"{base_folder}/{filename}", f"{folder_path}/copy_{filename}")

        create(self._input_dir)
        create(self._output_dir)

    def test1a1s(self):
        self._createTestFolder("1a1s", ("1a1s",))
        self._testFolder("1a1s_temp")

    @patch("easygui.indexbox")
    def test3a1s(self, mock_indexbox):
        mock_indexbox.return_value = 2
        self._createTestFolder("3a1s", ("3a1s",))
        self._testFolder("3a1s_temp")

    @patch("easygui.indexbox")
    def test3a2s(self, mock_indexbox):
        mock_indexbox.side_effect = [1, 2]
        self._createTestFolder("3a2s", ("3a2s",))
        self._testFolder("3a2s_temp")

    def test1a0s(self):
        # No need for copies because there are multiple 1a0s files
        self._createTestFolder("1a0s", ("1a0s",), False)
        self._testFolder("1a0s_temp")

    def testAudio(self):
        # No need for copies again
        self._createTestFolder("audio", ("audio",), False)
        self._testFolder("audio_temp")

    @patch("easygui.indexbox")
    def testMix(self, mock_indexbox):
        mock_indexbox.side_effect = [2, 1, 2]
        self._createTestFolder("mix", ("1a1s", "3a1s", "3a2s"))
        self._testFolder("mix_temp")

    def testFixedOutputDir(self):
        self._createTestFolder("1a1s", ("1a1s",))
        current_directory = os.getcwd()
        output_dir = op.join(current_directory, "test_out")
        config_set("fixed_output_dir", output_dir)
        self._testFolder("1a1s_temp", out_test_dir=output_dir)

    def testFixedOutputDirNoSubfolder(self):
        self._createTestFolder("1a1s", ("1a1s",))
        current_directory = os.getcwd()
        output_dir = op.join(current_directory, "test_out")
        config_set(("fixed_output_dir", "fixed_output_dir_with_subfolders"), (output_dir, False))
        self._testFolder("1a1s_temp", out_test_dir=output_dir, subfolder=False)

    @patch("easygui.indexbox")
    def testSubtitleOutput(self, mock_indexbox):
        mock_indexbox.side_effect = [2, 1, 2]
        config_set("output_condensed_subtitles", True)
        self._createTestFolder("mix", ("1a1s", "3a1s", "3a2s"))
        self._testFolder("mix_temp")

    @patch("easygui.diropenbox")
    @patch("easygui.buttonbox")
    def testWithGUISelection(self, mock_buttonbox, mock_diropenbox):
        folder_name = "1a1s_temp"
        mock_buttonbox.return_value = "Folder"
        mock_diropenbox.return_value = f"{self._input_dir}/{folder_name}"

        self._createTestFolder("1a1s", ("1a1s",))
        main()
        self._checkOutput(folder_name)


class TestErrors(unittest.TestCase):
    _input_dir = "test_files/inputs"
    _delete_outputs = True

    @staticmethod
    def getLog():
        with open("log.txt", "r", encoding="utf-8") as f:
            return f.read()

    def tearDown(self):
        restore_config()
        if self._delete_outputs:
            os.remove("log.txt")

    def _testFile(self, filename):
        print(caller_function_name())
        try:
            main(f"{self._input_dir}/{filename}")
        except Exception as e:
            self.fail(str(e))

    @patch("easygui.buttonbox")
    @patch("easygui.fileopenbox")
    def testNoInput(self, mock_fileopenbox, mock_buttonbox):
        # Simulate user closing the selection window
        mock_fileopenbox.return_value = None
        mock_buttonbox.return_value = 0

        main()
        self.assertTrue(op.exists("log.txt"))
        log = self.getLog()
        self.assertTrue("No input given" in log)

    def testNonExistentFile(self):
        main("test_files/inputs/nonexistent_file.mkv")
        self.assertFalse(op.exists("test_files/inputs/nonexistent_file_con.mp3"))
        self.assertTrue(op.exists("log.txt"))
        log = self.getLog()
        self.assertTrue("No such file or directory" in log)

    @patch("easygui.indexbox")
    def testNoAudioStreamSelection(self, mock_indexbox):
        # Simulate user closing the audio stream selection window
        mock_indexbox.return_value = None
        self._testFile("3a1s.mkv")
        self.assertFalse(op.exists("test_files/inputs/3a1s_con.mp3"))
        self.assertTrue(op.exists("log.txt"))
        log = self.getLog()
        self.assertTrue("Audio stream selection canceled" in log)
