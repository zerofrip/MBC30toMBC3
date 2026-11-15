"""Synthetic SRAM only: no ROM, game assets, or real player's save data."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from convert_save import convert, inspect_save, SaveError, write_output


def fixture(gender=0):
    data = bytearray((i * 17 + 13) % 256 for i in range(65536))
    for base in (0x2000, 0x7200):
        data[base + 8] = 0x63
        data[base + 0xD0F] = 0x7F
        data[base + 9:base + 17] = b"IDNAME00"
        checksum = sum(data[base + 9:base + 0xAE3]) & 65535
        data[base + 0xD0D:base + 0xD0F] = checksum.to_bytes(2, "little")
    data[0x8000] = gender
    data[0xA800] = 0
    return bytes(data)


class SaveConversionTests(unittest.TestCase):
    def test_exact_round_trip_with_original_template_both_genders(self):
        for gender in (0, 1):
            original = fixture(gender)
            small = convert(original, "mbc3")
            self.assertEqual(len(small), 32768)
            self.assertEqual(small[0x7F20:0x7F27], original[0x8000:0x8007])
            self.assertEqual(small[0x7F27:0x7F29], original[0x860E:0x8610])
            self.assertEqual(small[:0x7F20], original[:0x7F20])
            self.assertEqual(small[0x7F29:], original[0x7F29:0x8000])
            self.assertEqual(convert(small, "mbc30", original), original)

    def test_no_template_initializes_mobile_and_preserves_core(self):
        small = convert(fixture(1), "mbc3")
        large = convert(small, "mbc30")
        self.assertEqual(len(large), 65536)
        self.assertEqual(large[:0x7F20], small[:0x7F20])
        self.assertEqual(large[0x7F20:0x7F29], bytes(9))
        self.assertEqual(large[0x7F29:0x8000], small[0x7F29:])
        self.assertEqual(large[0x8000:0x8007], small[0x7F20:0x7F27])
        self.assertEqual(large[0x8007:], bytes(65536 - 0x8007))

    def test_changed_game_progress_wins_over_old_template(self):
        original = fixture()
        small = bytearray(convert(original, "mbc3"))
        # Simulate a legitimate save after play: update both copies + checksum.
        for base in (0x2000, 0x7200):
            small[base + 0x100] ^= 37
            small[base + 0xD0D:base + 0xD0F] = (sum(small[base + 9:base + 0xAE3]) & 65535).to_bytes(2, "little")
        small[0x7F21] ^= 9
        small[0x7F27:0x7F29] = bytes(2)
        large = convert(bytes(small), "mbc30", original)
        self.assertEqual(large[:0x7F20], small[:0x7F20])
        self.assertEqual(large[0x8001], small[0x7F21])
        self.assertEqual(large[0x860E:0x8610], bytes(2))
        self.assertEqual(large[0x9000:], original[0x9000:])

    def test_one_valid_copy_is_preserved_without_repair(self):
        for bad_base in (0x2000, 0x7200):
            original = bytearray(fixture())
            original[bad_base + 0x100] ^= 1
            small = convert(bytes(original), "mbc3")
            self.assertEqual(small[:0x7F20], original[:0x7F20])
            self.assertEqual(sum(inspect_save(small, "mbc3")["valid_copies"].values()), 1)

    def test_invalid_sizes_headers_checksums_gender_and_pending_trade(self):
        cases = [bytes(65536), bytes(32768), fixture() + b"RTC", fixture()[:-1]]
        for offsets in ((0x2008, 0x7208), (0x2D0F, 0x7F0F), (0x2100, 0x7300), (0x8000,), (0xA800,)):
            data = bytearray(fixture())
            for offset in offsets:
                data[offset] ^= 0xFF
            cases.append(bytes(data))
        for data in cases:
            with self.subTest(size=len(data)), self.assertRaises(SaveError):
                convert(data, "mbc3")

    def test_mismatched_trainer_template_is_rejected(self):
        other = bytearray(fixture())
        for base in (0x2000, 0x7200):
            other[base + 9] ^= 1
            other[base + 0xD0D:base + 0xD0F] = (sum(other[base + 9:base + 0xAE3]) & 65535).to_bytes(2, "little")
        with self.assertRaises(SaveError):
            convert(convert(fixture(), "mbc3"), "mbc30", bytes(other))

    def test_pending_template_and_template_in_wrong_direction_rejected(self):
        small = convert(fixture(), "mbc3")
        old = bytearray(fixture()); old[0xA800] = 1
        with self.assertRaises(SaveError):convert(small, "mbc30", bytes(old))
        with self.assertRaises(SaveError):convert(fixture(), "mbc3", fixture())

    def test_conflicting_valid_copy_identities_are_rejected(self):
        data = bytearray(fixture()); data[0x7209] ^= 1
        data[0x7F0D:0x7F0F] = (sum(data[0x7209:0x7CE3]) & 65535).to_bytes(2, "little")
        with self.assertRaises(SaveError):convert(bytes(data), "mbc3")

    def test_output_aliases_existing_files_and_dangling_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / "source.sav"
            original = fixture(); source.write_bytes(original)
            existing = root / "exists.sav"; existing.write_bytes(b"keep")
            hardlink = root / "hard.sav"; hardlink.hardlink_to(source)
            symlink = root / "sym.sav"; symlink.symlink_to(source)
            dangling = root / "dangling.sav"; dangling.symlink_to(root / "absent")
            for path in (source, existing, hardlink, symlink, dangling):
                with self.subTest(path=path.name), self.assertRaises(SaveError):
                    write_output(path, b"replacement", [source])
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(existing.read_bytes(), b"keep")
            self.assertFalse((root / "absent").exists())

    def test_cli_roundtrip_and_failure_leave_inputs_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); original = fixture(1)
            source = root / "source.sav"; source.write_bytes(original)
            small = root / "small.sav"; restored = root / "restored.sav"
            commands = [("to-mbc3", source, small, []),
                        ("to-mbc30", small, restored, ["--template", str(source)])]
            for direction, src, dst, extra in commands:
                result = subprocess.run([sys.executable, str(ROOT / "tools/convert_save.py"), direction,
                    str(src), "--output", str(dst), *extra], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(restored.read_bytes(), original)
            self.assertEqual(source.read_bytes(), original)
            bad = root / "bad.sav"; bad.write_bytes(b"invalid")
            result = subprocess.run([sys.executable, str(ROOT / "tools/convert_save.py"), "to-mbc3",
                str(bad), "--output", str(root / "not-created.sav")], capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse((root / "not-created.sav").exists())


if __name__ == "__main__":
    unittest.main()
