#!/usr/bin/env python3
"""
音声ファイルの前処理スクリプト

機能:
    1. m4a/mp3 → mp3 変換
    2. 無音部分の除去
    3. 1.5倍速に圧縮
    4. 60分を超える場合は自動分割

使用方法:
    python divide_voice.py audiofile.m4a
    python divide_voice.py audiofile.mp3
    python divide_voice.py audiofile.m4a -o output_dir
    python divide_voice.py audiofile.m4a --max-minutes 50

出力:
    output_dir/audiofile_optimized.mp3          （60分以内の場合）
    output_dir/audiofile_optimized_part1.mp3    （60分超の場合）
    output_dir/audiofile_optimized_part2.mp3
"""

import os
import sys
import subprocess
import argparse
import math


def get_duration(input_file: str) -> float:
    """音声ファイルの長さ（秒）を取得"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_file
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ ffprobe エラー: {result.stderr}")
        sys.exit(1)
    return float(result.stdout.strip())


def optimize_audio(input_file: str, output_file: str) -> str:
    """
    音声ファイルを最適化（mp3変換 + 無音除去 + 1.5倍速）

    Args:
        input_file: 入力ファイルパス
        output_file: 出力ファイルパス

    Returns:
        出力ファイルパス
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_file,
        "-af", "silenceremove=stop_periods=-1:stop_duration=1:stop_threshold=-40dB,atempo=1.5",
        output_file
    ]

    print(f"🔧 最適化中: mp3変換 + 無音除去 + 1.5倍速...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ ffmpeg エラー: {result.stderr}")
        sys.exit(1)

    return output_file


def split_audio(input_file: str, max_seconds: float) -> list:
    """
    音声ファイルを指定秒数ごとに分割

    Args:
        input_file: 入力ファイルパス
        max_seconds: 1パートの最大秒数

    Returns:
        分割されたファイルパスのリスト
    """
    duration = get_duration(input_file)
    num_parts = math.ceil(duration / max_seconds)

    if num_parts <= 1:
        return [input_file]

    base_name, ext = os.path.splitext(input_file)
    segment_seconds = duration / num_parts
    output_files = []

    print(f"✂️  {num_parts}分割（各パート約{segment_seconds/60:.1f}分）")

    for i in range(num_parts):
        start_time = i * segment_seconds
        part_num = i + 1
        output_file = f"{base_name}_part{part_num}{ext}"

        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_file,
            "-ss", str(start_time),
            "-t", str(segment_seconds),
            "-c", "copy",
            output_file
        ]

        print(f"   🔄 Part {part_num}: {start_time/60:.1f}分〜{(start_time+segment_seconds)/60:.1f}分")
        subprocess.run(cmd, capture_output=True)
        print(f"      ✅ {output_file}")

        output_files.append(output_file)

    return output_files


def process_audio(input_file: str, output_dir: str = None, max_minutes: float = 60) -> list:
    """
    音声ファイルを前処理して文字起こし用ファイルを生成

    Args:
        input_file: 入力ファイルパス
        output_dir: 出力ディレクトリ（Noneの場合は入力と同じ場所）
        max_minutes: 1パートの最大分数（デフォルト60分）

    Returns:
        処理後のファイルパスのリスト
    """
    # ファイル存在確認
    if not os.path.exists(input_file):
        print(f"❌ ファイルが見つかりません: {input_file}")
        sys.exit(1)

    # 出力先の設定
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    else:
        output_dir = os.path.dirname(input_file) or "."

    optimized_file = os.path.join(output_dir, f"{base_name}_optimized.mp3")

    # 元ファイルの情報
    original_duration = get_duration(input_file)
    print(f"📁 入力ファイル: {input_file}")
    print(f"⏱️  元の長さ: {original_duration/60:.1f}分")
    print("=" * 50)

    # Step 1: 最適化（mp3変換 + 無音除去 + 1.5倍速）
    optimize_audio(input_file, optimized_file)

    optimized_duration = get_duration(optimized_file)
    reduction = (1 - optimized_duration / original_duration) * 100
    print(f"⏱️  最適化後: {optimized_duration/60:.1f}分（{reduction:.0f}%削減）")

    # Step 2: 60分超なら分割
    max_seconds = max_minutes * 60
    if optimized_duration > max_seconds:
        print(f"⚠️  {max_minutes}分を超えるため分割します")
        output_files = split_audio(optimized_file, max_seconds)
        # 分割元の最適化ファイルは削除
        os.remove(optimized_file)
        print(f"🗑️  中間ファイル削除: {optimized_file}")
    else:
        output_files = [optimized_file]

    print("=" * 50)
    print(f"✅ 前処理完了: {len(output_files)}ファイル")
    for f in output_files:
        d = get_duration(f)
        print(f"   📄 {f} ({d/60:.1f}分)")

    return output_files


def main():
    parser = argparse.ArgumentParser(description="音声ファイルの前処理（mp3変換・無音除去・圧縮・分割）")
    parser.add_argument("audio_file", help="音声ファイルパス（m4a, mp3）")
    parser.add_argument("-o", "--output-dir", help="出力ディレクトリ（省略時は入力と同じ場所）")
    parser.add_argument("--max-minutes", type=float, default=60, help="1パートの最大分数（デフォルト: 60）")

    args = parser.parse_args()

    process_audio(args.audio_file, args.output_dir, args.max_minutes)


if __name__ == "__main__":
    main()