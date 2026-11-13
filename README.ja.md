# Pico Ocarina

[English](README.md) · [简体中文](README.zh-CN.md) · **日本語**

**Raspberry Pi Pico（RP2040）**をSwitchの有線コントローラーとして使い、オカリナの曲を自動演奏します。曲は基板に保存され、再生時はSwitchにつなぐだけです。

ファームウェア、Windows用の曲管理アプリ、MIDI変換ツールを収録しています。内蔵曲は「蛍の光（Auld Lang Syne）」で、56音、42.8秒、開始待ち3秒です。

## はじめに

1. [ファームウェア](firmware/Pico_Ocarina.uf2)をダウンロードします。BOOTSELを押しながらPicoをPCにつなぎ、UF2をRPI-RP2ドライブにコピーします。
2. PicoをSwitchにつなぎ、ゲームのオカリナ演奏画面を開きます。BOOTSELの短押しで再生・停止します。
3. 曲を変えるには[Launch.cmd](Launch.cmd)を開き、JSONを読み込むかMIDIを変換してPicoに転送します。

配線と転送の手順は[使い方](docs/GettingStarted.ja.md)をご覧ください。

## ボタン操作

| 操作 | 動作 |
|---|---|
| BOOTSELを短押し | 再生・停止 |
| 待機中にBOOTSELを約1秒長押し | L+Rを2回、続いてAを送り、コントローラー認識を進める |
| GP21とGNDをつないで電源を入れる | PC用の設定モードで起動し、曲を転送する |
| GP22とGNDの間に外付けボタンを接続 | BOOTSELと同じ再生操作 |

## 曲の管理アプリ

- **日本語・英語・簡体字中国語に対応。** ウィンドウ上部の言語欄で切り替えられ、選択は保存されます。初回はシステムの言語を使い、未対応の言語では英語になります。
- MIDIのトラックとチャンネルを選び、高音・低音の選択や試聴ができます。
- 時間範囲と18半音の音域枠をドラッグして、演奏する範囲を選べます。
- 曲のJSON、試聴MIDI、変換レポートを書き出せます。既存のJSONも直接読み込めます。
- シリアルポートでPicoに転送し、保存結果を読み戻して確認します。

WindowsではTcl/Tk付きのPython 3.9以降を使い、[Launch.cmd](Launch.cmd)または[PicoOcarina.pyw](PicoOcarina.pyw)を開いてください。必要な部品はアプリから、または次のコマンドでインストールできます。

```powershell
python -m pip install -r tools/requirements-gui.txt
```

言語を変えても、読み込んだJSON、音高、時刻、転送するデータは変わりません。内蔵のMIDI試聴はWindows用です。書き出したMIDIは別のプレーヤーでも開けます。

## ドキュメント

- [使い方](docs/GettingStarted.ja.md)：書き込み、再生、転送、よくある質問。
- [MIDI変換と曲の形式（英語）](docs/MIDIConversion.md)。
- [ビルド（英語）](docs/Building.md)。
- [第三者のライセンス表記（英語）](THIRD_PARTY.md)。プロジェクトのコードは[MITライセンス](LICENSE)です。
