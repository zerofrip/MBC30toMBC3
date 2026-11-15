# MBC30toMBC3 — 日本語版ポケットモンスター クリスタル

**未改造の日本語版クリスタル**を、標準MBC3の32KB SRAM＋RTCで動かすためのパッチ生成ソースです。EverDrive GB X7での利用を想定しています。

ROM・パッチ済みROM・IPS・セーブ・ゲーム画像はこのリポジトリに含めません。手元の日本語版ROMからローカルで生成します。英語版ROMは不要です。

## 最初に読む注意点

- **EverDrive GB X7実機での動作確認は未実施です。** エミュレータでの検証結果と実機の動作保証は異なります。
- **モバイルアダプタを使う通信機能は無効です。** モバイル交換、ニュース・オンライン配布、モバイルスタジアム、通信データが必要な日本語版バトルタワーなどは利用対象外です。オフライン代替イベントを追加するものではありません。
- **新規セーブで開始してください。** 性別などの保存先を移動するため、既存の64KB／32KBセーブは直接流用できません。移行ツールは含みません。元のROM・セーブを保管し、別のROM名を使ってください。
- **未改造の日本語版専用です。** Perfect Crystal RC5、251匹・60fps版、EZFlash JR修正済みROM、海外版、その他の改造版には使用しないでください。このリポジトリのパッチは重ねがけ用ではありません。
- 通常の通信ケーブル処理は変更していませんが、交換・対戦は未検証です。
- 全ストーリーの通しプレイ、実機での電源断後の保存、RTCの長時間経過、EverDriveのステートセーブは未検証です。
- 元の配信フラグを無効化するため、未改造日本語版のオンラインGSボール配布は利用できません。セレビィ入手イベントや251匹コンプリート機能は追加しません。
- 汎用的なMBC30→MBC3変換器ではありません。下記のROMハッシュに一致するものだけを受け付けます。

## 対象ROMと生成物

対象ファイル名の目安：`Pocket Monsters - Crystal Version (Japan).gbc`。判定には名前ではなくサイズとSHA-256を使用します。

| 対象 | サイズ | SHA-256 |
|---|---:|---|
| 未改造日本語版ROM | 2,097,152バイト | `136ada06cb68656b7de475fa4b278d37dbeff8f5257e7dfdf7f4a4aec19a90f3` |
| 生成IPS | 153バイト | `5e497d01fbe5037de88e3986e34498bf5e5d46b6a65bd4cb77df4bba63e00c1a` |
| パッチ適用後ROM | 2,097,152バイト | `9122ef3a80c7ab15ac4ece478a17d03f79aca3a4ce1e35fbd6c8650f8fef29ce` |

## ビルド

### 必要なもの

- Python 3（移設後の再現確認はPython 3.14）。
- RGBDS **0.3.4** の `rgbasm` と `rgblink`。他バージョンはこの構成では未検証。
- `lazy_ips` のチェックアウト（直下に `lazy_ips/patch/ips.py` がある構成）。IPS適用の検証に使用。
- `gb-asm-tools` のチェックアウト（直下に `tools/mapreader.py` がある構成）。アセンブルしたセクションの範囲を読むために使用。
- 上記ハッシュの日本語版ROM。

依存ツールは別途用意してください。第三者ツールのソースやライセンスは本リポジトリに再配布していません。各ツールのライセンスに従ってください。

以下はリポジトリ直下からの実行例です。`/path/to/...` は実際のローカルパスに置き換えます。コマンドはROMをネットワーク送信しません。

```sh
python3 tools/build.py \
  --rom '/path/to/Pocket Monsters - Crystal Version (Japan).gbc' \
  --lazy-ips '/path/to/lazy_ips' \
  --gb-asm-tools '/path/to/gb-asm-tools' \
  --rgbasm '/path/to/rgbds-0.3.4/rgbasm' \
  --rgblink '/path/to/rgbds-0.3.4/rgblink'
```

既定の出力先は `build/` です。`--out-dir` で変更できます。

- `candidate.ips`：未改造日本語版に適用するIPS。
- `candidate.gbc`：適用済みROM。ビルド時に生成されるので、さらにIPSを適用する必要はありません。
- `candidate.json`：入力・出力ハッシュ、変更範囲、実機未検証の情報。

ビルドは入力サイズ・ハッシュ、生成IPSとROMの既知ハッシュ、`lazy_ips`による再適用一致を検証します。入力ROMは変更しません。同じ内容の出力がある場合は再実行可能です。異なる既存出力・出力ファイルのシンボリックリンク・入力と同じ出力は拒否します。

### 生成IPSを別の未改造ROMコピーへ適用する場合

```sh
python3 tools/apply_patch.py '/path/to/original.gbc' \
  --patch build/candidate.ips \
  --lazy-ips '/path/to/lazy_ips' \
  --output build/applied.gbc
```

このツールも入力・IPS・出力のハッシュを確認します。一般的なIPS適用ソフトは入力ROMを検証しない場合があるため、上記の対象ハッシュを必ず確認してください。

## 実装内容

| 項目 | 変更 |
|---|---|
| ヘッダ | カートリッジ種別 `$10` を保持し、RAM容量を64KBから32KBに変更。チェックサムを再計算 |
| SRAM制御 | バンク0～3とRTCレジスタ8～12のみ許可し、無効なバンク選択時はSRAMを閉じる |
| 主人公情報 | バンク4の7バイトをバンク3の `$BF20`～`$BF26` に移動 |
| 通信フラグ | 保存先を `$BF27`～`$BF28` に移動し、ロード時は0にする |
| モバイル状態 | アダプタ未設定・交換預かりなし・オンライン配布なしを返す |
| コガネPCC | 読めないSRAMの値を分岐番号として使う停止と、GSボールの誤配布を防止 |
| 時計・表示 | RTC操作を保持。新しい英語表示は追加せず、日本語原版の文章・画像を使う |

通常のセーブ主領域・バックアップ・ボックスの配置は保持しています。

## 検証

```sh
# ROM不要のファイル保護テスト
python3 -m unittest discover -s tests -v

# PyBoyが必要。ビルド後、生成ROMのSM83 CPUテスト
python3 tools/verify_cpu.py --work-dir build

# 任意：非公開のテスト用セーブが必要
python3 tools/verify_play.py --work-dir build --fixture '/path/to/test-fixture.ram'
```

画面操作テストのfixtureは一般のプレイヤーのセーブでは代用できません。必要な状態とGhidraの実行例は [docs/VALIDATION.md](docs/VALIDATION.md) を参照してください。ROMやセーブを用意できない場合でもビルド用ソースは確認できますが、ゲーム動作テストは実行できません。

検証した範囲：SRAM選択512ケース、127のROMバンクからの呼び出しと復帰、RTCレジスタ、男女の情報保存・復元・新規セーブ初期化、男女×自宅／PCCの4ケースでのレポート保存・再起動・手持ち等の保持。

実ROMの解析にはGhidra/GhidraBoyおよび`pokemon-reverse-engineering-tools`、処理の意味の参照には`pokecrystal`を使用しました。未完成の`pokekuristaru`の配置を移植元にはしていません。`tools/ghidra/CrystalMbc3Audit.java` は生成ROMの対象命令を確認するためのスクリプトです。

## 収録範囲

- `src/patch.asm`：追加・差し替えコード。
- `tools/`：ビルド、IPS適用、CPU・画面操作検証、Ghidra監査。
- `tests/`：ROMを使わないファイル保護テスト。
- `docs/`：検証条件と制限。

ROM・IPS・セーブ・画面画像・逆アセンブルしたゲーム本体はコミット対象外です。生成物と依存ツールは`.gitignore`で除外します。本リポジトリのライセンスは既存の [LICENSE](LICENSE) を参照してください。ゲーム本体や第三者ツールに対する権利を付与するものではありません。
