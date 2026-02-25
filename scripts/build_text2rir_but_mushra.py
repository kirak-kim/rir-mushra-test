#!/usr/bin/env python3
import argparse
import contextlib
import csv
import html
import json
import os
import random
import sys
import wave
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build a webMUSHRA config for a text-to-RIR/image-to-RIR comparison on BUT-ReverbDB prompts."
    )
    p.add_argument(
        "--latest-root",
        default="/home/kirak/stable-audio-tools/whisperx_eval_hashmatch_rms_fair",
        help="Root with latest text-to-RIR eval outputs (contains gt/, gen/, level_stats.csv, manifests/).",
    )
    p.add_argument(
        "--baseline1-root",
        default="/home/kirak/stable-audio-tools/whisperx_eval_i2r_epoch48_hashmatch_rms_fair",
        help="Baseline #1 eval root (epoch48).",
    )
    p.add_argument(
        "--baseline2-root",
        default="/home/kirak/stable-audio-tools/whisperx_eval_i2r_official_hashmatch_rms_fair",
        help="Baseline #2 eval root (official ckpt).",
    )
    p.add_argument(
        "--anchor-dir",
        default="/home/kirak/stable-audio-tools/whisperx_eval_hashmatch_rms_fair/anchor_lp3500_from_gt",
        help="Directory with LP 3.5 kHz anchor wav files.",
    )
    p.add_argument(
        "--librispeech-root",
        default="/mnt/DATA0/dataset/LibriSpeech",
        help="LibriSpeech root (contains test-clean/...).",
    )
    p.add_argument(
        "--prompt-jsonl",
        default="/mnt/DATA0/dataset/BUT_ReverbDB/rir_prompts_split_peaknorm/test.jsonl",
        help="Prompt split JSONL with prompt + rir_file + rir_path.",
    )
    p.add_argument(
        "--pairs1-json",
        default="/home/kirak/image2reverb/infer_epoch48_test/pairs.json",
        help="Baseline #1 pairs.json containing image_path mapping.",
    )
    p.add_argument(
        "--pairs2-json",
        default="/home/kirak/image2reverb/infer_official_modelckpt_test/pairs.json",
        help="Baseline #2 pairs.json for optional consistency check.",
    )
    p.add_argument(
        "--output-config",
        default=str(REPO_ROOT / "configs/generated/text2rir_but_mushra.yaml"),
        help="Output YAML config path (prefer under configs/).",
    )
    p.add_argument(
        "--output-trial-csv",
        default=str(REPO_ROOT / "configs/generated/text2rir_but_mushra_trials.csv"),
        help="Output CSV with trial metadata used to generate the config.",
    )
    p.add_argument(
        "--link-root",
        default=str(REPO_ROOT / "external_data/text2rir_but_mushra"),
        help="Directory under webMUSHRA root where symlinks to audio/image data will be created.",
    )
    p.add_argument(
        "--num-trials",
        type=int,
        default=30,
        help="Number of trials to include (default: 30; use <=0 for all).",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed used when sampling trials.",
    )
    p.add_argument(
        "--sample-mode",
        choices=["random", "head"],
        default="random",
        help="Trial selection strategy before config generation.",
    )
    p.add_argument(
        "--reference-mode",
        choices=["dry", "latest_gt"],
        default="latest_gt",
        help="`dry`: LibriSpeech dry speech in reference button, `latest_gt`: latest BUT GT in reference button.",
    )
    p.add_argument(
        "--dry-ext",
        choices=["flac", "wav"],
        default="flac",
        help="Extension for LibriSpeech dry reference files when --reference-mode=dry.",
    )
    p.add_argument(
        "--show-waveform",
        action="store_true",
        help="Enable waveform view on MUSHRA pages.",
    )
    p.add_argument(
        "--disable-looping",
        action="store_true",
        help="Disable loop controls on MUSHRA pages.",
    )
    p.add_argument(
        "--show-condition-names",
        action="store_true",
        help="Show condition IDs to listeners (debug only; usually keep hidden).",
    )
    p.add_argument(
        "--no-condition-randomize",
        action="store_true",
        help="Disable within-page condition randomization.",
    )
    p.add_argument(
        "--test-id",
        default="text2rir_but_mushra",
        help="webMUSHRA testId.",
    )
    p.add_argument(
        "--test-name",
        default="Text-to-RIR / Image-to-RIR MUSHRA",
        help="webMUSHRA testname.",
    )
    p.add_argument(
        "--language",
        default="en",
        help="webMUSHRA UI language (buttons, labels). Default en.",
    )
    p.add_argument(
        "--remote-service",
        default="",
        help="Local result write endpoint (leave empty for GitHub Pages / Google Form only).",
    )
    p.add_argument(
        "--google-form-url",
        default="https://docs.google.com/forms/d/1rguxdGpyeVOqVA211_WAfwX0DQIy80wFyY-0GgA0znI/formResponse",
        help="Google Form formResponse endpoint (optional mirror upload).",
    )
    p.add_argument(
        "--google-form-entry-id",
        default="entry.294047297",
        help="Google Form entry ID that stores the serialized session JSON.",
    )
    p.add_argument(
        "--contact-phone",
        default="010-0000-0000",
        help="Phone number shown on the final thank-you/contact page.",
    )
    p.add_argument(
        "--no-write-results",
        action="store_true",
        help="Disable writing results to remote service.",
    )
    p.add_argument(
        "--show-results",
        action="store_true",
        help="Show raw results to participant on finish page (default: off).",
    )
    p.add_argument(
        "--no-symlinks",
        action="store_true",
        help="Do not create/update symlinks. Use if assets are already exposed by your web server.",
    )
    p.add_argument(
        "--no-align-audio-lengths",
        action="store_true",
        help="Skip per-trial WAV length alignment (zero-padding to max length).",
    )
    return p.parse_args()


def read_jsonl(path: Path) -> List[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def read_csv_dict(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def normalize_pairs_key_from_rir_path(rel_rir_path: str) -> str:
    # Example:
    # BUT_ReverbDB/VUT_FIT_L207/.../IR_sweep...v00.wav
    # -> VUT_FIT_L207__...__IR_sweep...v00
    key = rel_rir_path
    if key.startswith("BUT_ReverbDB/"):
        key = key[len("BUT_ReverbDB/") :]
    key = key.replace("/", "__")
    if key.endswith(".wav"):
        key = key[:-4]
    return key


def safe_rel_url(path_under_repo: Path) -> str:
    rel = path_under_repo.relative_to(REPO_ROOT)
    return rel.as_posix()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_symlink(link_path: Path, target: Path) -> None:
    if link_path.exists() or link_path.is_symlink():
        if link_path.exists() and link_path.is_dir() and not link_path.is_symlink():
            # Already bundled as a real directory for static hosting (e.g., GitHub Pages).
            return
        if link_path.is_symlink() and link_path.resolve() == target.resolve():
            return
        raise RuntimeError(f"Symlink path already exists and points elsewhere: {link_path}")
    os.symlink(str(target), str(link_path))


def yaml_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value)
    if s == "":
        return "''"
    s = s.replace("'", "''")
    return f"'{s}'"


def add_yaml_kv(lines: List[str], indent: int, key: str, value) -> None:
    lines.append(" " * indent + f"{key}: {yaml_scalar(value)}")


def add_yaml_block(lines: List[str], indent: int, key: str, text: str) -> None:
    lines.append(" " * indent + f"{key}: |-")
    block_indent = " " * (indent + 2)
    if not text:
        lines.append(block_indent)
        return
    for line in text.splitlines():
        lines.append(block_indent + line)


def build_intro_html(reference_mode: str) -> str:
    return "\n".join(
        [
            "<div class='t2r-context-card'>",
            "  <div class='t2r-context-label'>Experiment Guide / 실험 안내</div>",
            "  <p><strong>KO</strong> 본 연구는 AI로 생성하는 실내 음향을 평가하는 연구입니다. 생성된 각 실내에서 재생된 발화 음성이 얼마나 해당 공간과 어울리는지를 평가하는 실험입니다.</p>",
            "  <p><strong>EN</strong> This study evaluates AI-generated room acoustics. You will judge how well the speech sounds as if it were played in each generated room.</p>",
            "  <p><strong>KO</strong> 반드시 헤드폰/이어폰을 착용하고, 듣기 편한 적절한 볼륨으로 조절한 후 실험에 참여해 주세요.</p>",
            "  <p><strong>EN</strong> Please wear headphones/earphones and adjust to a comfortable, appropriate listening volume before starting the experiment.</p>",
            "  <p><strong>KO</strong> 각 페이지에서 방 이미지와 텍스트 설명을 보고, 제시된 condition 음성들 중 어떤 음성이 해당 공간의 음향적 특성을 잘 담고 있는지(해당 공간에서 재생되는 것 같은지) 평가해 주세요. 가장 좋은 점수는 100점, 가장 안 좋은 점수는 0점입니다.</p>",
            "  <p><strong>EN</strong> On each page, inspect the room image and text description, then rate which condition audio best captures that room's acoustic characteristics (i.e., sounds like it is being played in that room). The best score is 100 and the worst score is 0.</p>",
            "  <p><strong>KO</strong> Reference는 정답 오디오이며 들으시는 condition 중 하나는 reference와 완전히 동일합니다. 해당 condition은 100점으로 평가하셔야 합니다. 나머지 condition은 해당 원본의 퀄리티를 기준으로 상대적으로 자유롭게 평가해 주세요.</p>",
            "  <p><strong>EN</strong> The Reference is the correct audio, and one of the conditions is identical to the Reference. That condition should receive 100 points. Rate the other conditions freely relative to that original-quality reference.</p>",
            "  <p><strong>KO</strong> 품질이 확연히 낮은 신호가 포함되어 있을 수 있습니다.</p>",
            "  <p><strong>EN</strong> Clearly lower-quality signals may be included.</p>",
            "</div>",
        ]
    )


def build_participant_form_content_html() -> str:
    return "\n".join(
        [
            "<div class='t2r-context-card'>",
            "  <div class='t2r-context-label'>Participant Info / 참가자 정보</div>",
            "  <p><strong>KO</strong> 참가자 통계를 위해 나이와 성별을 입력해 주세요. 개인 식별 목적이 아니며 실험 통계 집계에만 사용됩니다.</p>",
            "  <p><strong>EN</strong> Please provide your age and gender for participant statistics. This is used for aggregated analysis only.</p>",
            "</div>",
        ]
    )


def build_practice_trial_html() -> str:
    return "\n".join(
        [
            "<div class='t2r-context-card'>",
            "  <div class='t2r-context-label'>Practice Trial / 연습 Trial</div>",
            "  <p><strong>KO</strong> 이 페이지에서 조작법을 익힌 뒤 다음 페이지부터 본 실험이 시작됩니다.</p>",
            "  <p><strong>EN</strong> Use this page to learn the controls. The main experiment starts on the next page.</p>",
            "  <p><strong>KO</strong> Reference 아래에 있는 재생 버튼을 눌러 정답 오디오를 들으시고, 왼쪽의 condition audio들도 재생해 보세요.</p>",
            "  <p><strong>EN</strong> Press the play button under Reference to hear the correct audio, then try playing the condition audios on the left.</p>",
            "  <p><strong>KO</strong> 연습 페이지의 Condition 중 하나는 Reference(정답 신호)와 동일합니다. 그 Condition에는 반드시 100점을 주고, 그 100점을 기준으로 나머지 Condition들을 상대적으로 평가해 보세요.</p>",
            "  <p><strong>EN</strong> One practice condition is identical to the Reference (correct signal). Give that condition a score of 100, then rate the remaining conditions relative to that 100-point reference.</p>",
            "  <p><strong>KO</strong> 좌측의 <strong>Stop</strong> 버튼은 전체 재생을 멈춥니다.</p>",
            "  <p><strong>EN</strong> The <strong>Stop</strong> button on the left stops playback.</p>",
            "  <p><strong>KO</strong> 각 조건 버튼을 누르면 해당 음원이 재생됩니다. 다른 조건으로 바꿔도 처음부터 다시 시작되지 않고, 같은 시간 위치에서 이어서 재생됩니다.</p>",
            "  <p><strong>EN</strong> Press condition buttons to play sounds. Switching conditions does not restart from the beginning; playback continues from the same time position.</p>",
            "  <p><strong>KO</strong> 좌우의 큰 슬라이더는 재생 구간을 설정하고, 상하 슬라이더는 점수 입력용입니다.</p>",
            "  <p><strong>EN</strong> The large left-right sliders set the playback region, and the up-down sliders are used for scoring.</p>",
            "  <p><strong>KO</strong> 여러 버튼을 눌러보면서 적응해 보세요. 연습 trial 결과는 제출되지 않습니다.</p>",
            "  <p><strong>EN</strong> Try multiple buttons to get comfortable. Practice-trial responses are not submitted.</p>",
            "</div>",
        ]
    )


def build_trial_content_html(trial_idx: int, total_trials: int, row: dict) -> str:
    prompt = html.escape(row["prompt"])
    image_url = html.escape(row["image_url"])
    speech_text = html.escape(row.get("speech_text", ""))

    speech_block = ""
    if speech_text:
        speech_block = (
            "      <div class='t2r-context-label'>Speech Transcript / 음성 내용</div>\n"
            f"      <div class='t2r-context-meta'>{speech_text}</div>\n"
        )

    return "\n".join(
        [
            "<div class='t2r-context-card'>",
            "  <div>",
            "    <div class='t2r-context-label'>Text Description / 텍스트 설명</div>",
            f"    <div class='t2r-context-prompt'>{prompt}</div>",
            speech_block.rstrip("\n"),
            "    <div class='t2r-context-image-center-wrap'>",
            "      <div class='t2r-context-label'>Room Image / 공간 이미지</div>",
            f"      <img class='t2r-context-image t2r-context-image-centered' src='{image_url}' alt='Room image for trial {trial_idx}' />",
            "    </div>",
            "    <div class='t2r-context-note'>",
            "      KO: 이미지/프롬프트와의 일치도와 자연스러움을 기준으로 평가해 주세요. Reference와 동일한 condition은 100점을 줘야 하며, 그에 상대적으로 다른 음성들의 점수를 매겨 주세요.<br/>",
            "      EN: Rate based on match to the image/text description and naturalness. The condition identical to the Reference should receive 100, and other conditions should be scored relative to it.",
            "    </div>",
            "  </div>",
            "</div>",
        ]
    ).replace("\n\n", "\n")


def build_finish_html(contact_phone: str) -> str:
    return "\n".join(
        [
            "<div class='t2r-context-card'>",
            "  <div class='t2r-context-label'>Thank You / 감사합니다</div>",
            "  <p style='text-align:center; margin:0.4em 0 0.9em 0;'><img class='t2r-thankyou-image' src='design/images/epic.jpg' alt='Thank you image' /></p>",
            "  <p><strong>KO</strong> 참여해 주셔서 감사합니다. 아래 제출 버튼을 눌러 결과를 저장해 주세요.</p>",
            "  <p><strong>EN</strong> Thank you for participating. Please press submit below to save your results.</p>",
            "  <p><strong>KO</strong> 실험진행자(김기락)에게 연락 주시면 감사의 선물을 드리도록 하겠습니다! 한국에 계신 분들께는 바나나 우유 기프티콘, 토론토에 계신 분들께는 페레로 로쉐 한 알을 드릴 예정이며 카톡/dm 등으로 말씀 주세요! 실험 참여해주셔서 정말 감사합니다!</p>",
            "  <p><strong>EN</strong> Please contact the experiment organizer (G. Kim) for a small thank-you gift after participation. Thank you very much for taking part in the study!</p>",
            "</div>",
        ]
    )


def librispeech_rel_path(split: str, utt_id: str, ext: str) -> str:
    spk, chap, _ = utt_id.split("-", 2)
    return f"{split}/{spk}/{chap}/{utt_id}.{ext}"


def check_path_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def wav_nframes(path: Path) -> int:
    with contextlib.closing(wave.open(str(path), "rb")) as w:
        return w.getnframes()


def pad_wav_to_frames(path: Path, target_frames: int) -> int:
    with contextlib.closing(wave.open(str(path), "rb")) as w:
        params = w.getparams()
        current_frames = w.getnframes()
        raw = w.readframes(current_frames)

    if current_frames == target_frames:
        return 0

    frame_size = params.nchannels * params.sampwidth
    if current_frames < target_frames:
        raw += b"\x00" * ((target_frames - current_frames) * frame_size)
    else:
        raw = raw[: target_frames * frame_size]

    with contextlib.closing(wave.open(str(path), "wb")) as w:
        w.setparams(params)
        w.writeframes(raw)

    return target_frames - current_frames


def align_rows_audio_lengths(repo_root: Path, rows_for_config: List[dict]) -> Tuple[int, int, int]:
    changed_trials = 0
    changed_files = 0
    max_added_frames = 0

    for row in rows_for_config:
        paths = [repo_root / row["reference_url"]]
        for _, rel in row["audio_urls"].items():
            paths.append(repo_root / rel)

        # Deduplicate (reference and hidden ref can be same file).
        uniq_paths = []
        seen = set()
        for p in paths:
            sp = str(p)
            if sp in seen:
                continue
            seen.add(sp)
            uniq_paths.append(p)

        infos = []
        for p in uniq_paths:
            with contextlib.closing(wave.open(str(p), "rb")) as w:
                infos.append((p, w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()))

        if not infos:
            continue

        sr = infos[0][2]
        ch = infos[0][3]
        sw = infos[0][4]
        for p, nframes, psr, pch, psw in infos:
            if psr != sr or pch != ch or psw != sw:
                raise RuntimeError(
                    f"Cannot align due to format mismatch in trial {row.get('trial_index')}: {p}"
                )

        target_frames = max(info[1] for info in infos)
        if any(info[1] != target_frames for info in infos):
            changed_trials += 1

        for p, nframes, _, _, _ in infos:
            if nframes != target_frames:
                delta = pad_wav_to_frames(p, target_frames)
                changed_files += 1
                if delta > max_added_frames:
                    max_added_frames = delta

    return changed_trials, changed_files, max_added_frames


def load_eval_bundle(root: Path) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    stats_path = root / "level_stats.csv"
    gt_manifest = root / "manifests" / "gt.jsonl"
    check_path_exists(stats_path, "level_stats.csv")
    check_path_exists(gt_manifest, "gt.jsonl")

    stats_rows = read_csv_dict(stats_path)
    stats_by_utt = {r["utt_id"]: r for r in stats_rows}
    if len(stats_by_utt) != len(stats_rows):
        raise RuntimeError(f"Duplicate utt_id detected in {stats_path}")

    manifest_rows = read_jsonl(gt_manifest)
    manifest_by_utt = {r["utt_id"]: r for r in manifest_rows}
    return stats_by_utt, manifest_by_utt


def commonpath_from_files(paths: Iterable[str]) -> Path:
    plist = [str(Path(p)) for p in paths]
    if not plist:
        raise RuntimeError("No paths available to compute common root.")
    return Path(os.path.commonpath(plist))


def main() -> int:
    args = parse_args()

    latest_root = Path(args.latest_root)
    baseline1_root = Path(args.baseline1_root)
    baseline2_root = Path(args.baseline2_root)
    anchor_dir = Path(args.anchor_dir)
    librispeech_root = Path(args.librispeech_root)
    prompt_jsonl = Path(args.prompt_jsonl)
    pairs1_json = Path(args.pairs1_json)
    pairs2_json = Path(args.pairs2_json)
    output_config = Path(args.output_config)
    output_trial_csv = Path(args.output_trial_csv)
    link_root = Path(args.link_root)

    for label, path in [
        ("latest-root", latest_root),
        ("baseline1-root", baseline1_root),
        ("baseline2-root", baseline2_root),
        ("anchor-dir", anchor_dir),
        ("librispeech-root", librispeech_root),
        ("prompt-jsonl", prompt_jsonl),
        ("pairs1-json", pairs1_json),
        ("pairs2-json", pairs2_json),
    ]:
        check_path_exists(path, label)

    latest_stats, latest_manifest = load_eval_bundle(latest_root)
    b1_stats, _ = load_eval_bundle(baseline1_root)
    b2_stats, _ = load_eval_bundle(baseline2_root)

    utt_ids = sorted(latest_stats.keys())
    if set(b1_stats.keys()) != set(utt_ids) or set(b2_stats.keys()) != set(utt_ids):
        raise RuntimeError("utt_id set mismatch across latest/baseline eval roots.")

    prompt_rows = read_jsonl(prompt_jsonl)
    prompt_by_rir_file = {Path(r["rir_file"]).name: r for r in prompt_rows}

    with pairs1_json.open("r", encoding="utf-8") as f:
        pairs1 = json.load(f)
    with pairs2_json.open("r", encoding="utf-8") as f:
        pairs2 = json.load(f)

    # Build merged rows and validate joins.
    merged_rows = []
    missing_prompt = 0
    missing_pair = 0
    pair_mismatch = 0
    for utt_id in utt_ids:
        latest = latest_stats[utt_id]
        b1 = b1_stats[utt_id]
        b2 = b2_stats[utt_id]
        rir_gt_name = latest["rir_gt_name"]
        if b1["rir_gt_name"] != rir_gt_name or b2["rir_gt_name"] != rir_gt_name:
            raise RuntimeError(f"rir_gt_name mismatch across systems for utt_id={utt_id}")

        prompt_row = prompt_by_rir_file.get(rir_gt_name)
        if prompt_row is None:
            missing_prompt += 1
            continue

        pair_key = normalize_pairs_key_from_rir_path(prompt_row["rir_path"])
        p1 = pairs1.get(pair_key)
        p2 = pairs2.get(pair_key)
        if p1 is None or p2 is None:
            missing_pair += 1
            continue
        if p1.get("image_path") != p2.get("image_path"):
            pair_mismatch += 1

        manifest = latest_manifest.get(utt_id, {})
        speech_text = manifest.get("text", "")
        split = latest.get("split") or manifest.get("split") or "test-clean"

        merged_rows.append(
            {
                "utt_id": utt_id,
                "split": split,
                "rir_gt_name": rir_gt_name,
                "room_short": prompt_row.get("room_short", ""),
                "prompt": prompt_row["prompt"],
                "rir_path_rel": prompt_row["rir_path"],
                "rir_file_path": prompt_row["rir_file"],
                "image_path_abs": p1["image_path"],
                "speech_text": speech_text,
            }
        )

    if missing_prompt or missing_pair:
        raise RuntimeError(
            f"Join failed: missing_prompt={missing_prompt}, missing_pair={missing_pair}, merged={len(merged_rows)}"
        )
    if pair_mismatch:
        print(f"[WARN] pairs.json image_path mismatch count: {pair_mismatch} (using pairs1)", file=sys.stderr)

    if not merged_rows:
        raise RuntimeError("No merged rows available after joins.")

    # Trial sampling.
    rows = list(merged_rows)
    if args.sample_mode == "random":
        rng = random.Random(args.seed)
        rng.shuffle(rows)
    if args.num_trials and args.num_trials > 0:
        rows = rows[: args.num_trials]
    total_trials = len(rows)

    if total_trials == 0:
        raise RuntimeError("No trials selected (check --num-trials).")

    # Symlink roots that make external assets visible to webMUSHRA.
    # Use the common image root so individual image URLs can stay short and stable.
    image_root_abs = commonpath_from_files(r["image_path_abs"] for r in merged_rows)
    if image_root_abs.name.endswith(".jpg"):
        image_root_abs = image_root_abs.parent

    ensure_dir(output_config.parent)
    ensure_dir(output_trial_csv.parent)
    ensure_dir(link_root)

    link_targets = {
        "latest_gt": latest_root / "gt",
        "latest_gen": latest_root / "gen",
        "baseline1_gen": baseline1_root / "gen",
        "baseline2_gen": baseline2_root / "gen",
        "anchor_lp3500": anchor_dir,
        "but_images": image_root_abs,
    }
    if args.reference_mode == "dry":
        link_targets["librispeech"] = librispeech_root

    if not args.no_symlinks:
        # Remove stale symlinks from previous runs (important for GitHub Pages/Jekyll).
        for stale_name in ["baseline1_gt", "baseline2_gt", "librispeech"]:
            stale_path = link_root / stale_name
            if stale_name not in link_targets and stale_path.is_symlink():
                stale_path.unlink()
        for name, target in link_targets.items():
            check_path_exists(target, f"symlink target {name}")
            ensure_symlink(link_root / name, target)

    # URL base strings (repo-relative) used in config.
    link_root_rel = safe_rel_url(link_root)
    url_bases = {
        name: f"{link_root_rel}/{name}" for name in link_targets.keys()
    }

    # Build per-trial audio/image URLs and existence checks.
    rows_for_config = []
    for i, row in enumerate(rows, start=1):
        utt_id = row["utt_id"]
        split = row["split"]
        wav_name = f"{utt_id}__{split}.wav"

        audio_urls = {
            "T2R_GEN": f"{url_bases['latest_gen']}/{wav_name}",
            "B1_GEN": f"{url_bases['baseline1_gen']}/{wav_name}",
            "B2_GEN": f"{url_bases['baseline2_gen']}/{wav_name}",
            "ANCHOR_LP3500": f"{url_bases['anchor_lp3500']}/{wav_name}",
        }

        if args.reference_mode == "dry":
            dry_rel = librispeech_rel_path(split, utt_id, args.dry_ext)
            reference_url = f"{url_bases['librispeech']}/{dry_rel}"
            dry_abs = librispeech_root / dry_rel
            if not dry_abs.exists():
                raise FileNotFoundError(f"Dry reference missing for {utt_id}: {dry_abs}")
        else:
            reference_url = f"{url_bases['latest_gt']}/{wav_name}"

        image_abs = Path(row["image_path_abs"])
        image_rel = image_abs.relative_to(image_root_abs).as_posix()
        image_url = f"{url_bases['but_images']}/{image_rel}"

        # Local existence checks for selected trial audio files.
        for label, abs_path in [
            ("T2R_GT", latest_root / "gt" / wav_name),
            ("T2R_GEN", latest_root / "gen" / wav_name),
            ("B1_GT", baseline1_root / "gt" / wav_name),
            ("B1_GEN", baseline1_root / "gen" / wav_name),
            ("B2_GT", baseline2_root / "gt" / wav_name),
            ("B2_GEN", baseline2_root / "gen" / wav_name),
            ("ANCHOR_LP3500", anchor_dir / wav_name),
            ("IMAGE", image_abs),
        ]:
            if not abs_path.exists():
                raise FileNotFoundError(f"{label} file missing for {utt_id}: {abs_path}")

        out = dict(row)
        out["reference_url"] = reference_url
        out["image_url"] = image_url
        out["audio_urls"] = audio_urls
        out["trial_index"] = i
        rows_for_config.append(out)

    # Trial CSV for traceability / analysis.
    with output_trial_csv.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "trial_index",
            "utt_id",
            "split",
            "room_short",
            "rir_gt_name",
            "rir_path_rel",
            "rir_file_path",
            "image_path_abs",
            "image_url",
            "reference_url",
            "prompt",
            "speech_text",
        ] + [f"stim_{k}" for k in ["T2R_GEN", "B1_GEN", "B2_GEN", "ANCHOR_LP3500"]]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows_for_config:
            flat = {k: row.get(k, "") for k in fieldnames}
            for k, v in row["audio_urls"].items():
                flat[f"stim_{k}"] = v
            w.writerow(flat)

    # Build YAML config.
    pages = []
    pages.append(
        {
            "type": "participant_form",
            "id": "participant_info",
            "name": "Participant Info / 참가자 정보",
            "content": build_participant_form_content_html(),
            "validationMessage": "Please complete age and gender / 나이와 성별을 입력해 주세요.",
            "questionnaire": [
                {
                    "type": "number",
                    "label": "Age / 나이",
                    "name": "age",
                    "min": 1,
                    "max": 120,
                },
                {
                    "type": "likert",
                    "label": "Gender / 성별",
                    "name": "gender",
                    "response": [
                        {"value": "female", "label": "Female / 여성"},
                        {"value": "male", "label": "Male / 남성"},
                        {"value": "nonbinary", "label": "Non-binary / 논바이너리"},
                        {"value": "prefer_not_to_say", "label": "Prefer not to say / 응답 안 함"},
                    ],
                },
            ],
        }
    )
    pages.append(
        {
            "type": "generic",
            "id": "intro_ko_en",
            "name": "Instructions / 안내",
            "content": build_intro_html(args.reference_mode),
        }
    )
    pages.append(
        {
            "type": "mushra",
            "id": "practice_trial_controls",
            "name": "Practice Trial",
            "content": build_practice_trial_html(),
            "showWaveform": bool(args.show_waveform),
            "enableLooping": not args.disable_looping,
            "strict": False,
            "reference": "configs/resources/audio/mono_ref.wav",
            "createAnchor35": False,
            "createAnchor70": False,
            "randomize": False,
            "showConditionNames": True,
            "stimuli": {
                "Practice_A": "configs/resources/audio/mono_c1.wav",
                "Practice_B": "configs/resources/audio/mono_c2.wav",
                "Practice_C": "configs/resources/audio/mono_c3.wav",
            },
            "switchBack": False,
        }
    )

    for row in rows_for_config:
        pages.append(
            {
                "type": "mushra",
                "id": f"trial_{row['trial_index']:03d}_{row['utt_id']}",
                "name": f"Trial {row['trial_index']}",
                "content": build_trial_content_html(row["trial_index"], total_trials, row),
                "showWaveform": bool(args.show_waveform),
                "enableLooping": not args.disable_looping,
                "strict": False,
                "reference": row["reference_url"],
                "createAnchor35": False,
                "createAnchor70": False,
                "randomize": not args.no_condition_randomize,
                "showConditionNames": bool(args.show_condition_names),
                "stimuli": row["audio_urls"],
                "switchBack": False,
            }
        )

    pages.append(
        {
            "type": "finish",
            "name": "Finish / 종료",
            "content": build_finish_html(args.contact_phone),
            "popupContent": "Thank you / 감사합니다",
            "showResults": bool(args.show_results),
            "writeResults": not args.no_write_results,
        }
    )

    lines: List[str] = []
    add_yaml_kv(lines, 0, "testname", args.test_name)
    add_yaml_kv(lines, 0, "testId", args.test_id)
    add_yaml_kv(lines, 0, "language", args.language)
    add_yaml_kv(lines, 0, "bufferSize", 2048)
    add_yaml_kv(lines, 0, "stopOnErrors", True)
    add_yaml_kv(lines, 0, "showButtonPreviousPage", True)
    add_yaml_kv(lines, 0, "remoteService", args.remote_service)
    if args.google_form_url and args.google_form_entry_id:
        add_yaml_kv(lines, 0, "googleFormUrl", args.google_form_url)
        add_yaml_kv(lines, 0, "googleFormEntryId", args.google_form_entry_id)
    lines.append("")
    lines.append("pages:")

    for page in pages:
        lines.append(f"    - type: {yaml_scalar(page['type'])}")
        if "id" in page:
            add_yaml_kv(lines, 6, "id", page["id"])
        add_yaml_kv(lines, 6, "name", page["name"])
        add_yaml_block(lines, 6, "content", page.get("content", ""))

        if page["type"] == "mushra":
            for key in [
                "showWaveform",
                "enableLooping",
                "strict",
                "reference",
                "createAnchor35",
                "createAnchor70",
                "randomize",
                "showConditionNames",
            ]:
                add_yaml_kv(lines, 6, key, page[key])
            lines.append("      stimuli:")
            for stim_name, stim_url in page["stimuli"].items():
                add_yaml_kv(lines, 10, stim_name, stim_url)
            add_yaml_kv(lines, 6, "switchBack", page["switchBack"])
        elif page["type"] == "participant_form":
            if "validationMessage" in page:
                add_yaml_kv(lines, 6, "validationMessage", page["validationMessage"])
            lines.append("      questionnaire:")
            for q in page["questionnaire"]:
                lines.append("          - type: " + yaml_scalar(q["type"]))
                add_yaml_kv(lines, 12, "label", q["label"])
                add_yaml_kv(lines, 12, "name", q["name"])
                if q["type"] == "number":
                    if "min" in q:
                        add_yaml_kv(lines, 12, "min", q["min"])
                    if "max" in q:
                        add_yaml_kv(lines, 12, "max", q["max"])
                    if "default" in q:
                        add_yaml_kv(lines, 12, "default", q["default"])
                elif q["type"] == "likert":
                    lines.append("            response:")
                    for item in q["response"]:
                        lines.append("             - value: " + yaml_scalar(item["value"]))
                        add_yaml_kv(lines, 15, "label", item["label"])
        elif page["type"] == "finish":
            add_yaml_kv(lines, 6, "popupContent", page["popupContent"])
            add_yaml_kv(lines, 6, "showResults", page["showResults"])
            add_yaml_kv(lines, 6, "writeResults", page["writeResults"])

    output_config.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if not args.no_align_audio_lengths:
        changed_trials, changed_files, max_added_frames = align_rows_audio_lengths(REPO_ROOT, rows_for_config)
        print(
            f"[INFO] Audio length alignment: trials_adjusted={changed_trials}, "
            f"files_padded={changed_files}, max_added_frames={max_added_frames}"
        )

    print(f"[OK] Wrote config: {output_config}")
    print(f"[OK] Wrote trial CSV: {output_trial_csv}")
    print(f"[INFO] Trials selected: {total_trials} / {len(merged_rows)}")
    print(f"[INFO] Link root: {link_root} (symlinks {'disabled' if args.no_symlinks else 'enabled'})")
    if args.reference_mode == "dry" and args.dry_ext == "flac":
        print(
            "[WARN] Dry reference uses LibriSpeech FLAC. If your browser cannot decode FLAC in webMUSHRA, convert to WAV and rerun with --dry-ext wav.",
            file=sys.stderr,
        )
    print(
        "[INFO] Load with: http://<server>/index.html?config=generated/"
        + output_config.name
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
