#!/usr/bin/env python3
"""
議事録作成パイプライン

指定フォルダ内の音声ファイル（m4a, mp3）を一括で文字起こしする。

処理フロー:
    1. フォルダ内の音声ファイルを検出
    2. 前処理（mp3変換・無音除去・1.5倍速・自動分割）
    3. 各パートを順番に文字起こし
    4. 全パートの結果を1つのファイルに結合
    5. 中間ファイルを削除

使用方法:
    python run.py /path/to/audio/folder
    python run.py /path/to/audio/folder --keep-intermediate
    python run.py /path/to/audio/folder --max-minutes 50

出力:
    /path/to/audio/folder/
        ├── 元の音声ファイル.m4a（そのまま）
        ├── 元の音声ファイル_result.txt（結合済み結果）
        ├── 元の音声ファイル_optimized_part1_result.txt（パート別結果）
        └── 元の音声ファイル_optimized_part2_result.txt（パート別結果）
"""

import os
import sys
import glob
import argparse

from divide_voice import process_audio
from transcribe_test import upload_to_gcs, transcribe_with_diarization, format_output, BUCKET_NAME


# 対応する音声ファイルの拡張子
AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav", ".flac", ".ogg"}

# スキップ対象のファイル名パターン（処理済みの中間ファイル）
SKIP_PATTERNS = {"_optimized", "_part"}


def find_audio_files(folder: str) -> list:
    """
    フォルダ内の音声ファイルを検出（中間ファイルは除外）

    Args:
        folder: 検索対象フォルダ

    Returns:
        音声ファイルパスのリスト
    """
    audio_files = []
    for f in sorted(os.listdir(folder)):
        name, ext = os.path.splitext(f)
        if ext.lower() not in AUDIO_EXTENSIONS:
            continue
        # 中間ファイルをスキップ
        if any(pattern in name for pattern in SKIP_PATTERNS):
            continue
        audio_files.append(os.path.join(folder, f))
    return audio_files


def transcribe_file(audio_file: str) -> str:
    """
    1つの音声ファイルを文字起こし

    Args:
        audio_file: 音声ファイルパス

    Returns:
        文字起こし結果テキスト
    """
    print(f"\n🎤 文字起こし中: {audio_file}")

    # GCSにアップロード
    audio_uri = upload_to_gcs(audio_file, BUCKET_NAME)

    # 文字起こし実行
    utterances = transcribe_with_diarization(audio_uri)

    # 結果を整形
    output_text = format_output(utterances)

    # パート別の結果を保存
    base_name = os.path.splitext(audio_file)[0]
    result_file = f"{base_name}_result.txt"
    with open(result_file, "w", encoding="utf-8") as f:
        f.write(output_text)
    print(f"   📄 保存: {result_file}")

    return output_text


def merge_results(results: list, output_file: str):
    """
    複数パートの結果を1つのファイルに結合

    Args:
        results: 各パートの結果テキストのリスト
        output_file: 出力ファイルパス
    """
    merged = "\n\n".join(
        f"--- Part {i+1} ---\n{text}" for i, text in enumerate(results) if text.strip()
    )

    # パートが1つだけの場合はセパレータなし
    if len(results) == 1:
        merged = results[0]

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(merged)
    print(f"📝 結合結果を保存: {output_file}")


def cleanup_intermediate(files: list):
    """中間ファイルを削除"""
    for f in files:
        if os.path.exists(f):
            os.remove(f)
            print(f"🗑️  削除: {f}")


def process_folder(folder: str, max_minutes: float = 60, keep_intermediate: bool = False):
    """
    フォルダ内の音声ファイルを一括処理

    Args:
        folder: 対象フォルダパス
        max_minutes: 1パートの最大分数
        keep_intermediate: 中間ファイルを残すか
    """
    # フォルダ存在確認
    if not os.path.isdir(folder):
        print(f"❌ フォルダが見つかりません: {folder}")
        sys.exit(1)

    # 音声ファイルを検出
    audio_files = find_audio_files(folder)
    if not audio_files:
        print(f"⚠️  音声ファイルが見つかりません: {folder}")
        print(f"   対応形式: {', '.join(AUDIO_EXTENSIONS)}")
        sys.exit(1)

    print("=" * 60)
    print("🎙️  議事録作成パイプライン")
    print("=" * 60)
    print(f"📂 対象フォルダ: {folder}")
    print(f"🔍 検出ファイル: {len(audio_files)}件")
    for f in audio_files:
        print(f"   📄 {os.path.basename(f)}")
    print("=" * 60)

    # 各ファイルを処理
    for audio_file in audio_files:
        print(f"\n{'='*60}")
        print(f"📁 処理開始: {os.path.basename(audio_file)}")
        print(f"{'='*60}")

        base_name = os.path.splitext(os.path.basename(audio_file))[0]
        merged_result_file = os.path.join(folder, f"{base_name}_result.txt")

        # Step 1: 前処理（mp3変換・無音除去・圧縮・分割）
        optimized_files = process_audio(audio_file, output_dir=folder, max_minutes=max_minutes)

        # Step 2: 各パートを順番に文字起こし
        results = []
        for part_file in optimized_files:
            result_text = transcribe_file(part_file)
            results.append(result_text)

        # Step 3: 結果を結合
        merge_results(results, merged_result_file)

        # Step 4: 中間ファイルの削除
        if not keep_intermediate:
            intermediate_files = []
            for part_file in optimized_files:
                intermediate_files.append(part_file)
                # パート別の結果ファイルは残す（両方残す仕様）
            cleanup_intermediate(intermediate_files)

        print(f"\n✅ 完了: {os.path.basename(audio_file)}")
        print(f"   📝 結合結果: {merged_result_file}")

    print(f"\n{'='*60}")
    print(f"🎉 全ファイルの処理が完了しました")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="議事録作成パイプライン: 音声ファイルの前処理〜文字起こしを一括実行"
    )
    parser.add_argument("folder", help="音声ファイルが入ったフォルダパス")
    parser.add_argument(
        "--max-minutes", type=float, default=60,
        help="1パートの最大分数（デフォルト: 60）"
    )
    parser.add_argument(
        "--keep-intermediate", action="store_true",
        help="中間ファイル（最適化済みmp3）を残す"
    )

    args = parser.parse_args()

    process_folder(args.folder, args.max_minutes, args.keep_intermediate)


if __name__ == "__main__":
    main()
