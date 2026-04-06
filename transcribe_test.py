#!/usr/bin/env python3
"""
Google Cloud Speech-to-Text V2 Chirp 3
話者識別付き文字起こしスクリプト

使用方法:
    python transcribe_test.py audio.wav
    
出力:
    audio_result.txt （入力ファイル名 + _result.txt）
"""

import os
import sys
import argparse
from google.cloud import storage
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech
from google.api_core.client_options import ClientOptions


# === 設定 ===
PROJECT_ID = "speech-transcription-483505"
BUCKET_NAME = "my-plaud-audio-bucket-12345"
REGION = "asia-northeast1"


def upload_to_gcs(local_file_path: str, bucket_name: str) -> str:
    """
    ローカルファイルをGCSにアップロード
    
    Returns:
        GCS URI (gs://bucket/filename)
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    
    # ファイル名を取得
    file_name = os.path.basename(local_file_path)
    blob = bucket.blob(file_name)
    
    print(f"📤 GCSにアップロード中: {local_file_path} -> gs://{bucket_name}/{file_name}")
    blob.upload_from_filename(local_file_path)
    print("✅ アップロード完了")
    
    return f"gs://{bucket_name}/{file_name}"


def transcribe_with_diarization(audio_uri: str) -> list:
    """
    話者識別付きで文字起こし
    
    Args:
        audio_uri: GCS URI (gs://bucket/file)
    
    Returns:
        話者ごとの発話リスト
    """
    # クライアント初期化
    client = SpeechClient(
        client_options=ClientOptions(
            api_endpoint=f"{REGION}-speech.googleapis.com",
        )
    )
    
    # 話者識別の設定
    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        language_codes=["ja-JP"],
        model="chirp_3",
        features=cloud_speech.RecognitionFeatures(
            enable_automatic_punctuation=True,
            # 話者ダイアライゼーションを有効化
            diarization_config=cloud_speech.SpeakerDiarizationConfig(),
        ),
    )
    
    file_metadata = cloud_speech.BatchRecognizeFileMetadata(uri=audio_uri)
    
    request = cloud_speech.BatchRecognizeRequest(
        recognizer=f"projects/{PROJECT_ID}/locations/{REGION}/recognizers/_",
        config=config,
        files=[file_metadata],
        recognition_output_config=cloud_speech.RecognitionOutputConfig(
            inline_response_config=cloud_speech.InlineOutputConfig(),
        ),
    )
    
    print("🎤 Chirp 3 で話者識別付き文字起こしを実行中...")
    print("   （数分かかる場合があります）")
    
    operation = client.batch_recognize(request=request)
    response = operation.result(timeout=600)
    
    print("✅ 文字起こし完了")
    
    # 結果をパース
    return parse_diarization_results(response.results[audio_uri].transcript.results)


def parse_diarization_results(results) -> list:
    """
    話者識別結果をパースして整形
    """
    utterances = []
    
    for result in results:
        if not result.alternatives:
            continue
        
        alternative = result.alternatives[0]
        words = alternative.words if alternative.words else []
        
        if not words:
            # 単語レベルの話者情報がない場合
            utterances.append({
                "speaker": "話者?",
                "text": alternative.transcript.strip(),
            })
            continue
        
        # 単語ごとの話者タグから発話を組み立て
        current_speaker = None
        current_words = []
        
        for word_info in words:
            speaker = word_info.speaker_label or "?"
            
            if speaker != current_speaker:
                if current_words:
                    utterances.append({
                        "speaker": f"話者{current_speaker}",
                        "text": "".join(current_words).strip(),
                    })
                current_speaker = speaker
                current_words = [word_info.word]
            else:
                current_words.append(word_info.word)
        
        # 最後の発話
        if current_words:
            utterances.append({
                "speaker": f"話者{current_speaker}",
                "text": "".join(current_words).strip(),
            })
    
    return utterances


def format_output(utterances: list) -> str:
    """
    発話リストをテキスト形式に整形
    """
    lines = []
    for u in utterances:
        lines.append(f"{u['speaker']}: {u['text']}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="話者識別付き文字起こし")
    parser.add_argument("audio_file", help="音声ファイルパス")
    
    args = parser.parse_args()
    
    # ファイル存在確認
    if not os.path.exists(args.audio_file):
        print(f"❌ ファイルが見つかりません: {args.audio_file}")
        sys.exit(1)
    
    # 出力ファイル名を自動生成（audio.wav → audio_result.txt）
    base_name = os.path.splitext(args.audio_file)[0]
    output_file = f"{base_name}_result.txt"
    
    print("=" * 50)
    print("話者識別付き文字起こし（Chirp 3）")
    print("=" * 50)
    
    # 1. GCSにアップロード
    audio_uri = upload_to_gcs(args.audio_file, BUCKET_NAME)
    
    # 2. 文字起こし実行
    utterances = transcribe_with_diarization(audio_uri)
    
    # 3. 結果を整形
    output_text = format_output(utterances)
    
    print("\n" + "=" * 50)
    print("📝 結果")
    print("=" * 50)
    print(output_text)
    print("=" * 50)
    
    # 4. ファイルに保存
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output_text)
    print(f"\n📁 保存しました: {output_file}")


if __name__ == "__main__":
    main()