# 議事録作成ツール (Gijiroku)

Google Cloud Speech-to-Text V2 (Chirp 3) を使った、話者識別付き文字起こしツールです。

## 機能

- 音声ファイル（m4a, mp3）を自動で前処理（mp3変換・無音除去・1.5倍速圧縮）
- 60分を超える音声は自動分割
- 話者識別（ダイアライゼーション）付きで文字起こし
- フォルダ指定で一括処理
- パート別・結合済みの両方の結果を出力

## 必要なもの

### システム要件

- Python 3.10+
- ffmpeg

### Python パッケージ

```bash
pip install google-cloud-speech google-cloud-storage
```

### Google Cloud セットアップ

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. Speech-to-Text API を有効化
3. Cloud Storage バケットを作成
4. 認証の設定（以下のいずれか）:
   - `gcloud auth application-default login` を実行
   - サービスアカウントキーを作成し、環境変数を設定:
     ```bash
     export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
     ```

### 設定の変更

`transcribe_test.py` 内の以下を自分の環境に合わせて変更してください:

```python
PROJECT_ID = "your-project-id"
BUCKET_NAME = "your-bucket-name"
REGION = "asia-northeast1"
```

## 使い方

### 一括処理（推奨）

フォルダに音声ファイルを入れて実行するだけ:

```bash
# フォルダを作って音声ファイルを配置
mkdir meeting_20260402
cp 会議録音.m4a meeting_20260402/

# 一括処理
python run.py meeting_20260402/
```

#### オプション

```bash
# 中間ファイル（最適化済みmp3）を残す
python run.py meeting_20260402/ --keep-intermediate

# 1パートの最大分数を変更（デフォルト: 60分）
python run.py meeting_20260402/ --max-minutes 50
```

### 個別実行

前処理と文字起こしを別々に実行することもできます:

```bash
# Step 1: 前処理（mp3変換・無音除去・圧縮・分割）
python divide_voice.py 会議録音.m4a -o output_dir/

# Step 2: 文字起こし
python transcribe_test.py output_dir/会議録音_optimized.mp3
```

## 出力ファイル

```
meeting_20260402/
├── 会議録音.m4a                              # 元の音声（そのまま）
├── 会議録音_result.txt                       # 結合済みの文字起こし結果
├── 会議録音_optimized_part1_result.txt       # パート1の結果
└── 会議録音_optimized_part2_result.txt       # パート2の結果
```

## 処理フロー

```
音声ファイル (m4a/mp3)
  ↓
前処理 (divide_voice.py)
  ├── mp3 に変換
  ├── 無音部分を除去 (1秒以上の無音, -40dB以下)
  ├── 1.5倍速に圧縮
  └── 60分超なら自動分割
  ↓
文字起こし (transcribe_test.py)
  ├── GCS にアップロード
  ├── Chirp 3 で話者識別付き文字起こし
  └── 結果をテキスト保存
  ↓
結合・整理 (run.py)
  ├── パート別結果を結合
  └── 中間ファイルを削除
```

## 料金目安

- **Speech-to-Text**: $0.016/分（月60分まで無料）
- **Cloud Storage**: 5GB まで無料（米国リージョン）
- 1.5時間の会議 → 無音除去+圧縮で約45分 → 無料枠内に収まる可能性あり

## ファイル構成

| ファイル | 説明 |
|---|---|
| `run.py` | 一括処理パイプライン |
| `divide_voice.py` | 音声前処理（変換・圧縮・分割） |
| `transcribe_test.py` | 話者識別付き文字起こし |
| `README.md` | このファイル |

## 注意事項

- Chirp 3 は限定プレビューの場合があります。利用できない場合は `model="chirp_2"` に変更してください
- m4a 形式は Chirp 3 で正しく認識されない場合があるため、mp3 に変換して処理しています
- 長時間音声は分割して処理するため、パート境界で発話が途切れる場合があります