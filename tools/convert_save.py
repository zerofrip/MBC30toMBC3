"""日本語版クリスタル用：64KB MBC30と本プロジェクトの32KB MBC3セーブを相互変換。"""
import argparse
import hashlib
import os
from pathlib import Path

SIZE = {"mbc3": 0x8000, "mbc30": 0x10000}
CRYSTAL_MBC3 = 0x7F20
CRYSTAL_MBC30 = 0x8000
FLAGS_MBC30 = 0x860E
# Verified against the original Japanese ROM's bank-5 save/checksum routines.
COPIES = (("main", 0x2000), ("backup", 0x7200))


class SaveError(ValueError):
    """An unsupported, corrupt, or unsafe save conversion."""


def inspect_save(data, kind):
    """Check raw SRAM size, JP save markers/checksums, and relocated gender."""
    if kind not in SIZE or len(data) != SIZE[kind]:
        raise SaveError(f"{kind}には{SIZE.get(kind, '?')}バイトの純SRAMが必要です。ヘッダ・RTC末尾・ステートは未対応です。")
    valid = {}
    identities = []
    for name, base in COPIES:
        checksum = sum(data[base + 9:base + 0xAE3]) & 0xFFFF
        stored = int.from_bytes(data[base + 0xD0D:base + 0xD0F], "little")
        valid[name] = (data[base + 8] == 0x63 and
                       data[base + 0xD0F] == 0x7F and checksum == stored)
        if valid[name]:
            # Trainer ID (2 bytes) + Japanese trainer name (6 bytes).
            identities.append(bytes(data[base + 9:base + 17]))
    if not identities:
        raise SaveError("主セーブ・バックアップとも日本語版の識別値またはチェックサムが不正です。")
    if len(set(identities)) != 1:
        raise SaveError("主セーブとバックアップの主人公情報が一致しません。ゲームで読み込み・保存してから再試行してください。")
    gender_at = CRYSTAL_MBC3 if kind == "mbc3" else CRYSTAL_MBC30
    if data[gender_at] not in (0, 1):
        raise SaveError("性別データが不正です。このMBC3パッチのセーブ配置か確認してください。")
    return {"valid_copies": valid, "identity": identities[0]}


def convert(data, target, template=None):
    """Convert without modifying inputs; a template restores omitted SRAM bytes."""
    if target not in SIZE:
        raise SaveError("変換先はmbc3またはmbc30です。")
    source = "mbc30" if target == "mbc3" else "mbc3"
    info = inspect_save(data, source)
    if target == "mbc3":
        if template is not None:
            raise SaveError("復元元64KBセーブの指定はMBC3→MBC30でのみ使用できます。")
        if data[0xA800] != 0:
            raise SaveError("モバイル交換の預かり状態が残っています。元のゲームで解消してから変換してください。")
        result = bytearray(data[:SIZE[target]])
        result[CRYSTAL_MBC3:CRYSTAL_MBC3 + 7] = data[CRYSTAL_MBC30:CRYSTAL_MBC30 + 7]
        result[CRYSTAL_MBC3 + 7:CRYSTAL_MBC3 + 9] = data[FLAGS_MBC30:FLAGS_MBC30 + 2]
    else:
        if template is None:
            # Start with unconfigured mobile status, no pending trade or GS Ball,
            # and zeroed rankings; their zero checksum matches the zero counters.
            result = bytearray(SIZE[target])
            padding = bytes(9)
        else:
            old = inspect_save(template, "mbc30")
            if old["identity"] != info["identity"]:
                raise SaveError("復元元64KBセーブの主人公ID・名前が入力と一致しません。")
            if template[0xA800] != 0:
                raise SaveError("復元元にモバイル交換の預かり状態が残っています。古い取引状態は復元できません。")
            result = bytearray(template)
            padding = template[CRYSTAL_MBC3:CRYSTAL_MBC3 + 9]
        result[:SIZE["mbc3"]] = data
        result[CRYSTAL_MBC3:CRYSTAL_MBC3 + 9] = padding
        result[CRYSTAL_MBC30:CRYSTAL_MBC30 + 7] = data[CRYSTAL_MBC3:CRYSTAL_MBC3 + 7]
        # Without a template, flags referring to absent mobile data must be clear.
        result[FLAGS_MBC30:FLAGS_MBC30 + 2] = (
            data[CRYSTAL_MBC3 + 7:CRYSTAL_MBC3 + 9] if template is not None else bytes(2))
    inspect_save(result, target)
    return bytes(result)


def read_save(path, expected_size):
    # Bound reads and reject appended RTC data instead of silently dropping it.
    with path.open("rb") as stream:
        data = stream.read(expected_size + 1)
    if len(data) != expected_size:
        raise SaveError(f"{path.name}: 必要なサイズは{expected_size}バイトです。")
    return data


def write_output(path, data, inputs):
    for source in inputs:
        if path.resolve() == source.resolve() or (path.exists() and path.samefile(source)):
            raise SaveError("入力・復元元と同じファイルには出力できません。")
    # Exclusive creation rejects existing files and both live/dangling symlinks.
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise SaveError("出力先が既に存在します。別のファイル名を指定してください。") from exc
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("direction", choices=("to-mbc3", "to-mbc30"))
    parser.add_argument("input", type=Path, help="変換元の純SRAMセーブ")
    parser.add_argument("--output", type=Path, required=True, help="新規出力ファイル（上書き不可）")
    parser.add_argument("--template", type=Path, help="MBC30へ戻す際の元の64KBセーブ（任意）")
    args = parser.parse_args(argv)
    target = args.direction[3:]
    source = "mbc30" if target == "mbc3" else "mbc3"
    try:
        if target == "mbc3" and args.template is not None:
            raise SaveError("--templateはto-mbc30でのみ使用できます。")
        data = read_save(args.input, SIZE[source])
        template = read_save(args.template, SIZE["mbc30"]) if args.template else None
        info = inspect_save(data, source)
        output = convert(data, target, template)
        write_output(args.output, output, [args.input] + ([args.template] if args.template else []))
    except (SaveError, OSError) as exc:
        parser.exit(2, f"エラー: {exc}\n")
    print(f"変換完了: {args.output.name} ({len(output)}バイト)")
    print(f"SHA-256: {hashlib.sha256(output).hexdigest()}")
    if not all(info["valid_copies"].values()):
        print("注意: 有効なセーブが片側だけです。自動修復はしていません。ゲーム内で読み込み・保存してください。")
    if target == "mbc3":
        print("元の64KBセーブを保管してください。通信領域は32KB版に入りません。")
    elif template is None:
        print("復元元なし: 通信領域と通信フラグを0で初期化しました。過去の通信データは復元できません。")
    else:
        print("通信領域は復元元の時点の状態です。MBC3でのプレイによる通信履歴の更新は反映されません。")
    print("RTCの付加データ・別ファイル・実機の時計レジスタは変換していません。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
