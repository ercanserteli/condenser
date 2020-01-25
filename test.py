import subprocess as sp
import unittest
import os
import shutil


delete_outputs = True


class TestSingles(unittest.TestCase):
    def test1a1s(self):
        result = sp.run(["python", "condenser.py", "test_vids\\1a1s.mkv"], capture_output=True)
        msg = str(result.stdout) + "\n" + str(result.stderr)
        self.assertEqual(result.returncode, 0, msg)
        self.assertIn("Finished", str(result.stdout), msg)
        print(result.stdout)
        if delete_outputs:
            os.remove("test_vids\\1a1s_con.mp3")

    def test3a1s(self):
        result = sp.run(["python", "condenser.py", "test_vids\\3a1s.mkv"], capture_output=True)
        msg = str(result.stdout) + "\n" + str(result.stderr)
        self.assertEqual(result.returncode, 0, msg)
        self.assertIn("Finished", str(result.stdout), msg)
        print(result.stdout)
        if delete_outputs:
            os.remove("test_vids\\3a1s_con.mp3")

    # def test3a2s(self):
    #     result = sp.run(["python", "condenser.py", "test_vids\\3a2s.mkv"], capture_output=True)
    #     msg = str(result.stdout) + "\n" + str(result.stderr)
    #     self.assertEqual(result.returncode, 0, msg)
    #     self.assertIn("Finished", str(result.stdout), msg)
    #     print(result.stdout)
    #     if delete_outputs:
    #         os.remove("test_vids\\3a2s_con.mp3")

    def test1a0s(self):
        result = sp.run(["python", "condenser.py", "test_vids\\1a0s.mkv"], capture_output=True)
        msg = str(result.stdout) + "\n" + str(result.stderr)
        self.assertEqual(result.returncode, 0, msg)
        self.assertIn("Finished", str(result.stdout), msg)
        print(result.stdout)
        if delete_outputs:
            os.remove("test_vids\\1a0s_con.mp3")


class TestMultis(unittest.TestCase):
    def test1a1s(self):
        result = sp.run(["python", "condenser.py", "test_vids\\1a1s"], capture_output=True)
        msg = str(result.stdout) + "\n" + str(result.stderr)
        self.assertEqual(result.returncode, 0, msg)
        self.assertIn("Finished", str(result.stdout), msg)
        print(result.stdout)
        if delete_outputs:
            shutil.rmtree("test_vids\\1a1s_con", ignore_errors=True)

    def test3a1s(self):
        result = sp.run(["python", "condenser.py", "test_vids\\3a1s"], capture_output=True)
        msg = str(result.stdout) + "\n" + str(result.stderr)
        self.assertEqual(result.returncode, 0, msg)
        self.assertIn("Finished", str(result.stdout), msg)
        print(result.stdout)
        if delete_outputs:
            shutil.rmtree("test_vids\\3a1s_con", ignore_errors=True)

    def test3a2s(self):
        result = sp.run(["python", "condenser.py", "test_vids\\3a2s"], capture_output=True)
        msg = str(result.stdout) + "\n" + str(result.stderr)
        self.assertEqual(result.returncode, 0, msg)
        self.assertIn("Finished", str(result.stdout), msg)
        print(result.stdout)
        if delete_outputs:
            shutil.rmtree("test_vids\\3a2s_con", ignore_errors=True)

    def test1a0s(self):
        result = sp.run(["python", "condenser.py", "test_vids\\1a0s"], capture_output=True)
        msg = str(result.stdout) + "\n" + str(result.stderr)
        self.assertEqual(result.returncode, 0, msg)
        self.assertIn("Finished", str(result.stdout), msg)
        print(result.stdout)
        if delete_outputs:
            shutil.rmtree("test_vids\\1a0s_con", ignore_errors=True)

    def testmix(self):
        result = sp.run(["python", "condenser.py", "test_vids\\mix"], capture_output=True)
        msg = str(result.stdout) + "\n" + str(result.stderr)
        self.assertEqual(result.returncode, 0, msg)
        # self.assertIn("Videos in folder are not uniform", str(result.stdout), msg)
        self.assertIn("Finished", str(result.stdout), msg)
        print(result.stdout)
        if delete_outputs:
            shutil.rmtree("test_vids\\mix_con", ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
