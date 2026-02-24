#!/usr/bin/env python3
import argparse
import csv
import html
import json
import os
import random
import sys
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
        default=50,
        help="Number of trials to include (default: 50; use <=0 for all).",
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
        default="Text-to-RIR / Image-to-RIR MUSHRA (BUT-ReverbDB)",
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
    if reference_mode == "dry":
        ref_note_ko = "Reference 버튼은 원본 건조 음성(dry speech)입니다. 방의 정답 음향이 아니라 음성 내용 확인용입니다."
        ref_note_en = "The Reference button plays dry speech (original LibriSpeech). It is for speech-content clarity, not the target room acoustics."
    else:
        ref_note_ko = "Reference 버튼은 최신 시스템의 GT convolved speech입니다."
        ref_note_en = "The Reference button plays the latest-system GT convolved speech."

    return "\n".join(
        [
            "<div class='t2r-context-card'>",
            "  <div class='t2r-context-label'>Experiment Guide / 실험 안내</div>",
            "  <p><strong>KO</strong> 각 페이지에서 방 이미지와 프롬프트를 보고, 제시된 음성들 중 어떤 샘플이 해당 공간/프롬프트의 잔향 특성을 더 자연스럽게 반영하는지 평가해 주세요. 슬라이더는 높을수록 더 좋은 점수입니다.</p>",
            "  <p><strong>EN</strong> On each page, inspect the room image and prompt, then rate how well each presented speech sample matches the expected reverberation characteristics of that room/prompt. Higher scores mean better quality/match.</p>",
            f"  <p><strong>KO</strong> {html.escape(ref_note_ko)}</p>",
            f"  <p><strong>EN</strong> {html.escape(ref_note_en)}</p>",
            "  <p><strong>KO</strong> 조건 이름은 숨겨질 수 있으며 재생 순서는 무작위입니다.</p>",
            "  <p><strong>EN</strong> Condition identities may be hidden, and playback order is randomized.</p>",
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


def build_trial_content_html(trial_idx: int, total_trials: int, row: dict) -> str:
    prompt = html.escape(row["prompt"])
    image_url = html.escape(row["image_url"])
    utt_id = html.escape(row["utt_id"])
    room_short = html.escape(row.get("room_short", ""))
    rir_gt_name = html.escape(row["rir_gt_name"])
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
            "  <div class='t2r-context-grid'>",
            "    <figure class='t2r-context-image-wrap'>",
            "      <div class='t2r-context-label'>Room Image / 공간 이미지</div>",
            f"      <img class='t2r-context-image' src='{image_url}' alt='Room image for trial {trial_idx}' />",
            "    </figure>",
            "    <div>",
            "      <div class='t2r-context-label'>Prompt / 프롬프트</div>",
            f"      <div class='t2r-context-prompt'>{prompt}</div>",
            speech_block.rstrip("\n"),
            "      <div class='t2r-context-meta'>",
            f"        Trial {trial_idx}/{total_trials}<br/>",
            f"        utt_id: {utt_id}<br/>",
            f"        room: {room_short}<br/>",
            f"        rir_gt_name: {rir_gt_name}",
            "      </div>",
            "      <div class='t2r-context-note'>",
            "        KO: 이미지/프롬프트와의 잔향 일치도와 자연스러움을 기준으로 평가해 주세요.<br/>",
            "        EN: Rate based on reverberation match to the image/prompt and overall naturalness.",
            "      </div>",
            "    </div>",
            "  </div>",
            "</div>",
        ]
    ).replace("\n\n", "\n")


def build_finish_html(contact_phone: str) -> str:
    phone = html.escape(contact_phone)
    return "\n".join(
        [
            "<div class='t2r-context-card'>",
            "  <div class='t2r-context-label'>Thank You / 감사합니다</div>",
            "  <p><strong>KO</strong> 참여해 주셔서 감사합니다. 아래 제출 버튼을 눌러 결과를 저장해 주세요.</p>",
            "  <p><strong>EN</strong> Thank you for participating. Please press submit below to save your results.</p>",
            f"  <p><strong>KO</strong> 참가 선물을 받기 위해 연구자에게 연락해 주세요: <strong>{phone}</strong></p>",
            f"  <p><strong>EN</strong> To receive the participation gift, please contact the experimenter: <strong>{phone}</strong></p>",
            "</div>",
        ]
    )


def librispeech_rel_path(split: str, utt_id: str, ext: str) -> str:
    spk, chap, _ = utt_id.split("-", 2)
    return f"{split}/{spk}/{chap}/{utt_id}.{ext}"


def check_path_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


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
        "baseline1_gt": baseline1_root / "gt",
        "baseline1_gen": baseline1_root / "gen",
        "baseline2_gt": baseline2_root / "gt",
        "baseline2_gen": baseline2_root / "gen",
        "anchor_lp3500": anchor_dir,
        "librispeech": librispeech_root,
        "but_images": image_root_abs,
    }

    if not args.no_symlinks:
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
            "HIDDEN_REF_GT": f"{url_bases['latest_gt']}/{wav_name}",
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
            reference_url = audio_urls["HIDDEN_REF_GT"]

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
        ] + [f"stim_{k}" for k in ["HIDDEN_REF_GT", "T2R_GEN", "B1_GEN", "B2_GEN", "ANCHOR_LP3500"]]
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
