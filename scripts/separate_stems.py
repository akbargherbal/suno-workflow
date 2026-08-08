import os
import sys
import site
import argparse
import traceback
from pathlib import Path

# --- CUDA Shared Library Path Fix for Google Colab / Linux ONNX Runtime ---
cuda_lib_paths = ["/usr/local/cuda/lib64", "/usr/lib/x86_64-linux-gnu"]
for p in site.getsitepackages():
    nvidia_dir = os.path.join(p, "nvidia")
    if os.path.isdir(nvidia_dir):
        for root, dirs, _ in os.walk(nvidia_dir):
            if "lib" in dirs:
                cuda_lib_paths.append(os.path.join(root, "lib"))

# Filter to valid existing directories and sanitize LD_LIBRARY_PATH
valid_cuda_paths = [p for p in cuda_lib_paths if os.path.isdir(p)]
existing_ld = os.environ.get("LD_LIBRARY_PATH", "").strip(":")
if existing_ld:
    valid_cuda_paths.append(existing_ld)
os.environ["LD_LIBRARY_PATH"] = ":".join(valid_cuda_paths)
# -------------------------------------------------------------------

from audio_separator.separator import Separator

SUPPORTED_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg",
    ".wma", ".opus", ".aiff", ".aif", ".alac", ".mp4", ".webm", ".caf"
}


def process_audio_stems(
    input_path: str,
    output_base_dir: str = ".",
    model_filename: str = "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
    output_format: str = "MP3",
    output_bitrate: str = "320k",
    model_file_dir: str = None,
    recursive: bool = False
) -> dict:
    """
    Separates audio into Vocals and Instrumental stems.

    Args:
        input_path: Path to input audio file or directory.
        output_base_dir: Explicit output directory where results will be saved.
        model_filename: Audio separator model to use.
        output_format: Format for output stems (MP3, WAV, FLAC, etc.).
        output_bitrate: Bitrate for compressed audio formats (e.g., '320k').
        model_file_dir: Directory where model files will be downloaded/cached.
        recursive: If input_path is a directory, recursively scan subdirectories.

    Returns:
        Dict containing lists of 'successful' and 'failed' file processing records.
    """
    input_p = Path(input_path).expanduser().resolve()

    if not input_p.exists():
        raise FileNotFoundError(f"Error: Path '{input_path}' does not exist.")

    if input_p.is_file():
        if input_p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported audio format: '{input_p.suffix}'. "
                f"Supported formats: {sorted(SUPPORTED_EXTENSIONS)}"
            )
        audio_files = [input_p]
    elif input_p.is_dir():
        glob_pattern = "**/*" if recursive else "*"
        audio_files = sorted(
            [
                f for f in input_p.glob(glob_pattern)
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
            ],
            key=lambda p: p.name.lower()
        )
        if not audio_files:
            print(f"No supported audio files found in directory '{input_p}'.")
            return {"successful": [], "failed": []}
    else:
        raise ValueError(f"Invalid path type: '{input_path}'")

    print(f"Found {len(audio_files)} audio file(s) to process.")

    # Create explicit output base directory
    base_out_path = Path(output_base_dir).expanduser().resolve()
    base_out_path.mkdir(parents=True, exist_ok=True)
    print(f"Base output directory set to: {base_out_path}")

    # Configure separator kwargs
    separator_kwargs = {
        "output_format": output_format.upper(),
        "output_bitrate": output_bitrate,
        "log_level": 20
    }
    if model_file_dir:
        model_dir_path = Path(model_file_dir).expanduser().resolve()
        model_dir_path.mkdir(parents=True, exist_ok=True)
        separator_kwargs["model_file_dir"] = str(model_dir_path)

    separator = Separator(**separator_kwargs)

    print(f"\nLoading model '{model_filename}'...")
    separator.load_model(model_filename=model_filename)
    print("Model loaded successfully!\n")

    successful_files = []
    failed_files = []

    for idx, file_path in enumerate(audio_files, start=1):
        song_name = file_path.stem

        # Output directory: <output_base_dir>/<song_name>/
        song_output_dir = base_out_path / song_name
        song_output_dir.mkdir(parents=True, exist_ok=True)

        separator.output_dir = str(song_output_dir)
        # audio_separator caches output_dir on the loaded model_instance at
        # load_model() time, so the outer separator.output_dir alone is not
        # enough once a model has already been loaded — sync it explicitly.
        if separator.model_instance is not None:
            separator.model_instance.output_dir = str(song_output_dir)

        # Output key aliases for broad model architecture compatibility
        output_names = {
            "Vocals": f"{song_name}-Vocals",
            "Instrumental": f"{song_name}-Instrumental",
            "vocals": f"{song_name}-Vocals",
            "instrumental": f"{song_name}-Instrumental",
            "Primary": f"{song_name}-Instrumental",
            "Secondary": f"{song_name}-Vocals"
        }

        print(f"[{idx}/{len(audio_files)}] Processing: {file_path.name}")
        print(f"Destination: {song_output_dir}")

        try:
            separated_files = separator.separate(
                audio_file_path=str(file_path),
                custom_output_names=output_names
            )

            print(f"Completed '{song_name}':")
            for outfile in separated_files:
                print(f"  └─ {outfile}")
            successful_files.append((file_path, separated_files))
        except Exception as e:
            print(f"ERROR processing '{file_path.name}': {e}", file=sys.stderr)
            failed_files.append((file_path, str(e)))

        print("-" * 50)

    # Summary report
    print("\n" + "=" * 50)
    print(f"BATCH PROCESSING SUMMARY: {len(successful_files)} succeeded, {len(failed_files)} failed.")
    if failed_files:
        print("Failed files:")
        for fpath, err in failed_files:
            print(f"  - {fpath.name}: {err}")
    print("=" * 50)

    return {"successful": successful_files, "failed": failed_files}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Separate audio into Vocals and Instrumental stems.")
    parser.add_argument("input_path", type=str, help="Path to input audio file or directory.")
    parser.add_argument("-o", "--output_dir", type=str, default=".", help="Explicit destination directory for results (default: current directory).")
    parser.add_argument("-m", "--model", type=str, default="model_bs_roformer_ep_317_sdr_12.9755.ckpt", help="Separator model filename.")
    parser.add_argument("-f", "--format", type=str, default="MP3", help="Output format (MP3, WAV, FLAC, OGG, etc.).")
    parser.add_argument("-b", "--bitrate", type=str, default="320k", help="Output bitrate for compressed formats (e.g. 320k).")
    parser.add_argument("--model_dir", type=str, default=None, help="Directory to cache downloaded model files.")
    parser.add_argument("-r", "--recursive", action="store_true", help="Recursively search subdirectories if input_path is a directory.")

    args = parser.parse_args()

    process_audio_stems(
        input_path=args.input_path,
        output_base_dir=args.output_dir,
        model_filename=args.model,
        output_format=args.format,
        output_bitrate=args.bitrate,
        model_file_dir=args.model_dir,
        recursive=args.recursive
    )