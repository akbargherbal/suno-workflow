"""
Test suite for master_tracks.py

Run with:

    python3 -m pip install pytest
    python3 -m pytest tests/ -v

No real audio files or the `matchering` package are required — see
conftest.py for the fake `matchering` module used in place of the real
dependency.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest


# --------------------------------------------------------------------------
# build_results
# --------------------------------------------------------------------------

class TestBuildResults:
    def test_16bit(self, mt):
        results = mt.build_results(Path("/tmp/out.wav"), 16)
        assert len(results) == 1
        assert results[0].bit_depth == 16
        assert results[0].path == str(Path("/tmp/out.wav"))

    def test_24bit(self, mt):
        results = mt.build_results(Path("/tmp/out.wav"), 24)
        assert results[0].bit_depth == 24

    def test_invalid_bit_depth_raises(self, mt):
        with pytest.raises(ValueError, match="Unsupported bit depth"):
            mt.build_results(Path("/tmp/out.wav"), 32)


# --------------------------------------------------------------------------
# master_one
# --------------------------------------------------------------------------

class TestMasterOne:
    def test_calls_process_with_correct_paths(self, mt, fake_mg, tmp_path, audio_file):
        target = audio_file("target.wav")
        reference = audio_file("reference.wav")
        output = tmp_path / "out.wav"

        mt.master_one(target, reference, output, 16)

        assert len(fake_mg.process_calls) == 1
        call = fake_mg.process_calls[0]
        assert call["target"] == str(target)
        assert call["reference"] == str(reference)

    def test_creates_output_parent_dir(self, mt, tmp_path, audio_file):
        target = audio_file("target.wav")
        reference = audio_file("reference.wav")
        output = tmp_path / "nested" / "dir" / "out.wav"

        mt.master_one(target, reference, output, 16)

        assert output.exists()

    def test_respects_bit_depth(self, mt, fake_mg, tmp_path, audio_file):
        target = audio_file("target.wav")
        reference = audio_file("reference.wav")
        output = tmp_path / "out.wav"

        mt.master_one(target, reference, output, 24)

        result = fake_mg.process_calls[0]["results"][0]
        assert result.bit_depth == 24


# --------------------------------------------------------------------------
# master_batch
# --------------------------------------------------------------------------

class TestMasterBatch:
    def test_processes_only_audio_files(self, mt, fake_mg, tmp_path, audio_file):
        target_dir = tmp_path / "targets"
        target_dir.mkdir()
        (target_dir / "song1.wav").write_bytes(b"a")
        (target_dir / "song2.flac").write_bytes(b"b")
        (target_dir / "notes.txt").write_bytes(b"c")  # not audio, ignored
        (target_dir / "subdir").mkdir()  # dirs ignored

        reference = audio_file("reference.wav")
        output_dir = tmp_path / "out"

        mt.master_batch(target_dir, reference, output_dir, 16)

        assert len(fake_mg.process_calls) == 2
        outputs = sorted(p.name for p in output_dir.iterdir())
        assert outputs == ["song1_mastered.wav", "song2_mastered.wav"]

    def test_empty_target_dir_exits(self, mt, tmp_path, audio_file):
        target_dir = tmp_path / "targets"
        target_dir.mkdir()
        reference = audio_file("reference.wav")

        with pytest.raises(SystemExit, match="No audio files found"):
            mt.master_batch(target_dir, reference, tmp_path / "out", 16)

    def test_continues_after_one_track_fails(
        self, mt, tmp_path, audio_file, monkeypatch, caplog
    ):
        target_dir = tmp_path / "targets"
        target_dir.mkdir()
        (target_dir / "good.wav").write_bytes(b"a")
        (target_dir / "bad.wav").write_bytes(b"b")

        reference = audio_file("reference.wav")
        output_dir = tmp_path / "out"

        orig_master_one = mt.master_one

        def flaky_master_one(target, ref, output, bit_depth):
            if target.name == "bad.wav":
                raise RuntimeError("boom")
            return orig_master_one(target, ref, output, bit_depth)

        monkeypatch.setattr(mt, "master_one", flaky_master_one)

        caplog.set_level(logging.ERROR)
        mt.master_batch(target_dir, reference, output_dir, 16)

        assert (output_dir / "good_mastered.wav").exists()
        assert not (output_dir / "bad_mastered.wav").exists()
        assert "Failed to master bad.wav" in caplog.text


# --------------------------------------------------------------------------
# master_compare
# --------------------------------------------------------------------------

class TestMasterCompare:
    def test_creates_one_output_per_reference(self, mt, fake_mg, tmp_path, audio_file):
        target = audio_file("my_song.wav")
        ref_a = audio_file("ref_a.wav")
        ref_b = audio_file("ref_b.wav")
        output_dir = tmp_path / "comparisons"

        mt.master_compare(target, [ref_a, ref_b], output_dir, 16)

        assert len(fake_mg.process_calls) == 2
        outputs = sorted(p.name for p in output_dir.iterdir())
        assert outputs == ["ref_a__my_song.wav", "ref_b__my_song.wav"]

    def test_output_filenames_are_prefixed_by_reference(
        self, mt, tmp_path, audio_file
    ):
        target = audio_file("beat.wav")
        ref = audio_file("some_popular_song.wav")
        output_dir = tmp_path / "comparisons"

        mt.master_compare(target, [ref, audio_file("second_ref.wav")], output_dir, 16)

        assert (output_dir / "some_popular_song__beat.wav").exists()

    def test_dedupes_identical_references(self, mt, fake_mg, tmp_path, audio_file):
        target = audio_file("my_song.wav")
        ref_a = audio_file("ref_a.wav")
        output_dir = tmp_path / "comparisons"

        mt.master_compare(target, [ref_a, ref_a], output_dir, 16)

        assert len(fake_mg.process_calls) == 1

    def test_skips_missing_reference_but_continues(
        self, mt, fake_mg, tmp_path, audio_file, caplog
    ):
        target = audio_file("my_song.wav")
        ref_a = audio_file("ref_a.wav")
        missing_ref = tmp_path / "does_not_exist.wav"
        output_dir = tmp_path / "comparisons"

        caplog.set_level(logging.ERROR)
        mt.master_compare(target, [ref_a, missing_ref], output_dir, 16)

        assert len(fake_mg.process_calls) == 1
        assert "Reference file not found" in caplog.text

    def test_continues_after_one_reference_fails(
        self, mt, tmp_path, audio_file, monkeypatch, caplog
    ):
        target = audio_file("my_song.wav")
        ref_a = audio_file("ref_a.wav")
        ref_b = audio_file("ref_b.wav")
        output_dir = tmp_path / "comparisons"

        orig_master_one = mt.master_one

        def flaky_master_one(t, ref, output, bit_depth):
            if ref.name == "ref_a.wav":
                raise RuntimeError("boom")
            return orig_master_one(t, ref, output, bit_depth)

        monkeypatch.setattr(mt, "master_one", flaky_master_one)

        caplog.set_level(logging.ERROR)
        mt.master_compare(target, [ref_a, ref_b], output_dir, 16)

        outputs = sorted(p.name for p in output_dir.iterdir())
        assert outputs == ["ref_b__my_song.wav"]
        assert "Failed to master with reference ref_a.wav" in caplog.text


# --------------------------------------------------------------------------
# parse_args
# --------------------------------------------------------------------------

class TestParseArgs:
    def test_single(self, mt):
        args = mt.parse_args(["single", "t.wav", "r.wav", "o.wav", "-b", "24"])
        assert args.mode == "single"
        assert args.target == Path("t.wav")
        assert args.reference == Path("r.wav")
        assert args.output == Path("o.wav")
        assert args.bit_depth == 24

    def test_single_default_bit_depth(self, mt):
        args = mt.parse_args(["single", "t.wav", "r.wav", "o.wav"])
        assert args.bit_depth == 16

    def test_batch(self, mt):
        args = mt.parse_args(["batch", "targets/", "r.wav", "out/"])
        assert args.mode == "batch"
        assert args.target_dir == Path("targets/")
        assert args.reference == Path("r.wav")
        assert args.output_dir == Path("out/")

    def test_compare_with_repeated_r(self, mt):
        args = mt.parse_args(
            ["compare", "t.wav", "out/", "-r", "r1.wav", "-r", "r2.wav"]
        )
        assert args.mode == "compare"
        assert args.references == [Path("r1.wav"), Path("r2.wav")]
        assert args.reference_dir is None

    def test_compare_with_reference_dir(self, mt):
        args = mt.parse_args(["compare", "t.wav", "out/", "-d", "refs/"])
        assert args.reference_dir == Path("refs/")
        assert args.references == []

    def test_quiet_flag(self, mt):
        args = mt.parse_args(["-q", "single", "t.wav", "r.wav", "o.wav"])
        assert args.quiet is True

    def test_quiet_defaults_false(self, mt):
        args = mt.parse_args(["single", "t.wav", "r.wav", "o.wav"])
        assert args.quiet is False

    def test_invalid_bit_depth_rejected(self, mt):
        with pytest.raises(SystemExit):
            mt.parse_args(["single", "t.wav", "r.wav", "o.wav", "-b", "32"])

    def test_missing_mode_rejected(self, mt):
        with pytest.raises(SystemExit):
            mt.parse_args([])

    def test_unknown_mode_rejected(self, mt):
        with pytest.raises(SystemExit):
            mt.parse_args(["frobnicate", "t.wav", "r.wav", "o.wav"])


# --------------------------------------------------------------------------
# main() - single mode
# --------------------------------------------------------------------------

class TestMainSingle:
    def test_happy_path(self, mt, fake_mg, tmp_path, audio_file):
        target = audio_file("t.wav")
        reference = audio_file("r.wav")
        output = tmp_path / "out.wav"

        mt.main(["single", str(target), str(reference), str(output)])

        assert output.exists()
        assert len(fake_mg.process_calls) == 1

    def test_missing_target_exits(self, mt, tmp_path, audio_file):
        reference = audio_file("r.wav")
        with pytest.raises(SystemExit, match="Target file not found"):
            mt.main(
                ["single", str(tmp_path / "missing.wav"), str(reference), str(tmp_path / "o.wav")]
            )

    def test_missing_reference_exits(self, mt, tmp_path, audio_file):
        target = audio_file("t.wav")
        with pytest.raises(SystemExit, match="Reference file not found"):
            mt.main(
                ["single", str(target), str(tmp_path / "missing.wav"), str(tmp_path / "o.wav")]
            )


# --------------------------------------------------------------------------
# main() - batch mode
# --------------------------------------------------------------------------

class TestMainBatch:
    def test_happy_path(self, mt, tmp_path, audio_file):
        target_dir = tmp_path / "targets"
        target_dir.mkdir()
        (target_dir / "a.wav").write_bytes(b"x")
        reference = audio_file("r.wav")
        output_dir = tmp_path / "out"

        mt.main(["batch", str(target_dir), str(reference), str(output_dir)])

        assert (output_dir / "a_mastered.wav").exists()

    def test_missing_target_dir_exits(self, mt, tmp_path, audio_file):
        reference = audio_file("r.wav")
        with pytest.raises(SystemExit, match="Target folder not found"):
            mt.main(["batch", str(tmp_path / "nope"), str(reference), str(tmp_path / "out")])

    def test_missing_reference_exits(self, mt, tmp_path):
        target_dir = tmp_path / "targets"
        target_dir.mkdir()
        (target_dir / "a.wav").write_bytes(b"x")

        with pytest.raises(SystemExit, match="Reference file not found"):
            mt.main(
                ["batch", str(target_dir), str(tmp_path / "missing.wav"), str(tmp_path / "out")]
            )


# --------------------------------------------------------------------------
# main() - compare mode
# --------------------------------------------------------------------------

class TestMainCompare:
    def test_with_repeated_r_flags(self, mt, tmp_path, audio_file):
        target = audio_file("t.wav")
        ref_a = audio_file("ref_a.wav")
        ref_b = audio_file("ref_b.wav")
        output_dir = tmp_path / "comparisons"

        mt.main(
            ["compare", str(target), str(output_dir), "-r", str(ref_a), "-r", str(ref_b)]
        )

        outputs = sorted(p.name for p in output_dir.iterdir())
        assert outputs == ["ref_a__t.wav", "ref_b__t.wav"]

    def test_with_reference_dir(self, mt, tmp_path, audio_file):
        target = audio_file("t.wav")
        ref_dir = tmp_path / "refs"
        ref_dir.mkdir()
        (ref_dir / "ref_a.wav").write_bytes(b"x")
        (ref_dir / "ref_b.wav").write_bytes(b"y")
        (ref_dir / "notes.txt").write_bytes(b"z")  # ignored, not audio
        output_dir = tmp_path / "comparisons"

        mt.main(["compare", str(target), str(output_dir), "-d", str(ref_dir)])

        outputs = sorted(p.name for p in output_dir.iterdir())
        assert outputs == ["ref_a__t.wav", "ref_b__t.wav"]

    def test_combines_reference_dir_and_r_flags(self, mt, tmp_path, audio_file):
        target = audio_file("t.wav")
        ref_dir = tmp_path / "refs"
        ref_dir.mkdir()
        (ref_dir / "dir_ref.wav").write_bytes(b"x")
        extra_ref = audio_file("extra_ref.wav")
        output_dir = tmp_path / "comparisons"

        mt.main(
            [
                "compare", str(target), str(output_dir),
                "-d", str(ref_dir),
                "-r", str(extra_ref),
            ]
        )

        outputs = sorted(p.name for p in output_dir.iterdir())
        assert outputs == ["dir_ref__t.wav", "extra_ref__t.wav"]

    def test_requires_at_least_two_references(self, mt, tmp_path, audio_file):
        target = audio_file("t.wav")
        ref_a = audio_file("ref_a.wav")
        output_dir = tmp_path / "comparisons"

        with pytest.raises(SystemExit, match="at least two reference tracks"):
            mt.main(["compare", str(target), str(output_dir), "-r", str(ref_a)])

    def test_missing_target_exits(self, mt, tmp_path, audio_file):
        ref_a = audio_file("ref_a.wav")
        ref_b = audio_file("ref_b.wav")
        with pytest.raises(SystemExit, match="Target file not found"):
            mt.main(
                [
                    "compare",
                    str(tmp_path / "missing.wav"),
                    str(tmp_path / "out"),
                    "-r", str(ref_a),
                    "-r", str(ref_b),
                ]
            )

    def test_missing_reference_dir_exits(self, mt, tmp_path, audio_file):
        target = audio_file("t.wav")
        with pytest.raises(SystemExit, match="Reference folder not found"):
            mt.main(["compare", str(target), str(tmp_path / "out"), "-d", str(tmp_path / "nope")])

    def test_empty_reference_dir_exits(self, mt, tmp_path, audio_file):
        target = audio_file("t.wav")
        empty_ref_dir = tmp_path / "empty_refs"
        empty_ref_dir.mkdir()

        with pytest.raises(SystemExit, match="No audio files found"):
            mt.main(["compare", str(target), str(tmp_path / "out"), "-d", str(empty_ref_dir)])


# --------------------------------------------------------------------------
# main() - logging / quiet flag behaviour
# --------------------------------------------------------------------------

class TestMainLogging:
    def test_quiet_mode_skips_matchering_log_registration(
        self, mt, fake_mg, tmp_path, audio_file
    ):
        target = audio_file("t.wav")
        reference = audio_file("r.wav")
        output = tmp_path / "out.wav"

        mt.main(["-q", "single", str(target), str(reference), str(output)])

        assert fake_mg.logged == []

    def test_verbose_mode_registers_matchering_log(
        self, mt, fake_mg, tmp_path, audio_file
    ):
        target = audio_file("t.wav")
        reference = audio_file("r.wav")
        output = tmp_path / "out.wav"

        mt.main(["single", str(target), str(reference), str(output)])

        assert len(fake_mg.logged) == 1
