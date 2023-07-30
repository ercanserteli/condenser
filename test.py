import json
import subprocess as sp
import unittest
import os
import shutil
import inspect


delete_outputs = True


def current_function_name():
    return inspect.currentframe().f_back.f_code.co_name


def config_set(key, val):
    shutil.copy("config.json", "config.json.bak")
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    config[key] = val
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f)


def restore_config():
    if os.path.exists("config.json.bak"):
        shutil.copy("config.json.bak", "config.json")
        os.remove("config.json.bak")


def create_test_class(base_class, output_format):
    # noinspection PyPep8Naming
    class TestClass(base_class):
        _output_format = output_format

        @classmethod
        def setUpClass(cls):
            print("Setting output format to {}".format(cls._output_format))
            config_set("output_format", cls._output_format)

        @classmethod
        def tearDownClass(cls):
            super().tearDownClass()
            restore_config()

    return TestClass


class TestSinglesBase(unittest.TestCase):
    _output_format = "mp3"

    @classmethod
    def tearDownClass(cls):
        if delete_outputs:
            for filename in ["test_vids/1a1s_con", "test_vids/3a1s_con", "test_vids/1a0s_con"]:
                try:
                    os.remove("{}.{}".format(filename, cls._output_format))
                except Exception:
                    pass

    def test1a1s(self):
        print(current_function_name())
        result = sp.run(["python", "condenser.py", "test_vids/1a1s.mkv"], capture_output=True)
        msg = str(result.stdout) + "\n" + str(result.stderr)
        print(result.stdout)
        self.assertEqual(result.returncode, 0, msg)
        self.assertIn("Finished", str(result.stdout), msg)

    def test3a1s(self):
        print(current_function_name())
        result = sp.run(["python", "condenser.py", "test_vids/3a1s.mkv"], capture_output=True)
        msg = str(result.stdout) + "\n" + str(result.stderr)
        print(result.stdout)
        self.assertEqual(result.returncode, 0, msg)
        self.assertIn("Finished", str(result.stdout), msg)

    def test1a0s(self):
        print(current_function_name())
        result = sp.run(["python", "condenser.py", "test_vids/1a0s.mkv"], capture_output=True)
        msg = str(result.stdout) + "\n" + str(result.stderr)
        print(result.stdout)
        self.assertEqual(result.returncode, 0, msg)
        self.assertIn("Finished", str(result.stdout), msg)

    # def test3a2s(self):
    #     print(current_function_name())
    #     result = sp.run(["python", "condenser.py", "test_vids/3a2s.mkv"], capture_output=True)
    #     msg = str(result.stdout) + "\n" + str(result.stderr)
    #     print(result.stdout)
    #     self.assertEqual(result.returncode, 0, msg)
    #     self.assertIn("Finished", str(result.stdout), msg)


class TestFoldersBase(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        if delete_outputs:
            for filename in ["test_vids/1a1s_con", "test_vids/3a1s_con", "test_vids/3a2s_con", "test_vids/1a0s_con",
                             "test_vids/mix_con"]:
                shutil.rmtree(filename, ignore_errors=True)

    def test1a1s(self):
        print(current_function_name())
        result = sp.run(["python", "condenser.py", "test_vids/1a1s"], capture_output=True)
        msg = str(result.stdout) + "\n" + str(result.stderr)
        print(result.stdout)
        self.assertEqual(result.returncode, 0, msg)
        self.assertIn("Finished", str(result.stdout), msg)

    def test3a1s(self):
        print(current_function_name())
        result = sp.run(["python", "condenser.py", "test_vids/3a1s"], capture_output=True)
        msg = str(result.stdout) + "\n" + str(result.stderr)
        print(result.stdout)
        self.assertEqual(result.returncode, 0, msg)
        self.assertIn("Finished", str(result.stdout), msg)

    def test3a2s(self):
        print(current_function_name())
        result = sp.run(["python", "condenser.py", "test_vids/3a2s"], capture_output=True)
        msg = str(result.stdout) + "\n" + str(result.stderr)
        print(result.stdout)
        self.assertEqual(result.returncode, 0, msg)
        self.assertIn("Finished", str(result.stdout), msg)

    def test1a0s(self):
        print(current_function_name())
        result = sp.run(["python", "condenser.py", "test_vids/1a0s"], capture_output=True)
        msg = str(result.stdout) + "\n" + str(result.stderr)
        print(result.stdout)
        self.assertEqual(result.returncode, 0, msg)
        self.assertIn("Finished", str(result.stdout), msg)

    def testmix(self):
        print(current_function_name())
        result = sp.run(["python", "condenser.py", "test_vids/mix"], capture_output=True)
        msg = str(result.stdout) + "\n" + str(result.stderr)
        print(result.stdout)
        self.assertEqual(result.returncode, 0, msg)
        # self.assertIn("Videos in folder are not uniform", str(result.stdout), msg)
        self.assertIn("Finished", str(result.stdout), msg)


TestSinglesFLAC = create_test_class(TestSinglesBase, "flac")
TestFoldersFLAC = create_test_class(TestFoldersBase, "flac")


if __name__ == '__main__':
    unittest.main()
