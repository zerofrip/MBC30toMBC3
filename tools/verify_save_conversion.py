"""Local emulator verification; proprietary inputs are supplied explicitly."""
import argparse
import hashlib
import json
from io import BytesIO
from pathlib import Path
from pyboy import PyBoy
from build import BASE_SHA256, OUTPUT_SHA256
from convert_save import convert, inspect_save


def tick(game, n):
    game.tick(n, render=True, sound=False)


def press(game, button, frames=8):
    game.button_press(button); tick(game, frames)
    game.button_release(button); tick(game, 120)


def start(rom, save):
    game = PyBoy(BytesIO(rom), ram_file=BytesIO(save), window="null", sound_emulated=False)
    game.set_emulation_speed(0)
    tick(game, 600); press(game, "start")
    for _ in range(3): press(game, "a")
    tick(game, 200)
    return game


def battery(game, banks):
    output = bytearray(); game.memory[0] = 10
    for bank in range(banks):
        game.memory[0x4000] = bank
        output.extend(game.memory[0xA000:0xC000])
    game.memory[0] = 0
    return bytes(output)


def snapshot(game):
    return {"gender": game.memory[1, 0xD463],
            "identity": game.memory[1, 0xD48C:0xD494],
            "map": game.memory[1, 0xDC7B:0xDC7F],
            "party": game.memory[1, 0xDC9D:0xDE0D]}


def save_in_menu(game):
    press(game, "start")
    for _ in range(3): press(game, "down")
    for _ in range(3): press(game, "a")
    tick(game, 240)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-rom", type=Path, required=True)
    parser.add_argument("--mbc3-rom", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("build/conversion-tests"))
    args = parser.parse_args()
    original = args.original_rom.read_bytes(); patched = args.mbc3_rom.read_bytes()
    assert hashlib.sha256(original).hexdigest() == BASE_SHA256
    assert hashlib.sha256(patched).hexdigest() == OUTPUT_SHA256
    fixture = args.fixture.read_bytes(); inspect_save(fixture, "mbc30")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for gender in (0, 1):
        template = bytearray(fixture); template[0x8000] = gender; template = bytes(template)
        small = convert(template, "mbc3")
        assert convert(small, "mbc30", template) == template
        baseline = start(original, template)
        expected = snapshot(baseline); baseline.stop(save=False)
        game = start(patched, small)
        assert snapshot(game) == expected, "Forward conversion changed loaded game"
        press(game, "right", 24)
        assert snapshot(game)["map"] != expected["map"], "Test did not change progress"
        save_in_menu(game)
        progress = snapshot(game); saved = battery(game, 4); game.stop(save=False)
        inspect_save(saved, "mbc3")
        assert saved[0x4000:0x7200] == template[0x4000:0x7200]
        for mode in ("template", "initialized"):
            large = convert(saved, "mbc30", template if mode == "template" else None)
            game = start(original, large)
            assert snapshot(game) == progress, "Reverse conversion lost current progress"
            save_in_menu(game)
            resaved = battery(game, 8); game.stop(save=False)
            inspect_save(resaved, "mbc30")
            assert resaved[0x4000:0x7200] == template[0x4000:0x7200]
            final = start(patched, convert(resaved, "mbc3"))
            assert snapshot(final) == progress, "Roundtrip after saving lost progress"
            final.screen.image.save(str(args.out_dir / f"gender{gender}_{mode}.png"))
            final.stop(save=False)
            results.append({"gender": gender, "mode": mode, "passed": True})
    report = {"passed": True, "cases": results, "hardware_tested": False,
              "original_rom_sha256": BASE_SHA256, "mbc3_rom_sha256": OUTPUT_SHA256}
    (args.out_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
