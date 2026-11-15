"""Check file protection and early rejection without proprietary inputs."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build import write_new

class FileSafetyTests(unittest.TestCase):
    def test_conflict_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'output'
            write_new(path,b'first')
            write_new(path,b'first')
            with self.assertRaises(ValueError):write_new(path,b'second')
            self.assertEqual(path.read_bytes(),b'first')

    def test_symlink_is_rejected_even_for_identical_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'target';path.write_bytes(b'keep')
            alias=Path(directory)/'alias';alias.symlink_to(path)
            with self.assertRaises(ValueError):write_new(alias,b'keep')
            self.assertEqual(path.read_bytes(),b'keep')

    def test_unsupported_rom_rejected_before_tools_or_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);rom=root/'input.gbc';out=root/'output'
            for data in (b'not a ROM',bytes(0x200000)):
                with self.subTest(size=len(data)):
                    rom.write_bytes(data)
                    result=subprocess.run([sys.executable,str(ROOT/'tools/build.py'),
                        '--rom',str(rom),'--out-dir',str(out),
                        '--lazy-ips',str(root/'missing'),'--gb-asm-tools',str(root/'missing'),
                        '--rgbasm',str(root/'must-not-run')],capture_output=True,text=True)
                    self.assertNotEqual(result.returncode,0)
                    self.assertIn('Unsupported original ROM',result.stderr)
                    self.assertFalse(out.exists())
                    self.assertEqual(rom.read_bytes(),data)

if __name__=='__main__':unittest.main()
