# Text-to-RIR / Image-to-RIR MUSHRA Guide (KO/EN)

## 개요 (KO)
- 이 가이드는 `webMUSHRA-master`에서 BUT-ReverbDB 기반 `text-to-RIR` vs `image-to-RIR` 비교 MUSHRA 실험을 구성하는 방법을 설명합니다.
- 시작 시 참가자 정보(나이/성별) 입력 페이지를 보여주고, 각 trial 상단에 `Room image + Prompt`를 함께 표시하며, 마지막에 감사/연락 안내 페이지를 포함한 설정 파일을 자동 생성합니다.
- 기본 스크립트는 파일 경로를 질문에서 제공한 값으로 채워 두었습니다.

## Overview (EN)
- This guide explains how to run a BUT-ReverbDB-based MUSHRA test in `webMUSHRA-master` for `text-to-RIR` vs `image-to-RIR` comparisons.
- It auto-generates a config with a participant-info page (age/gender), trial pages showing `Room image + Prompt`, and a final thank-you/contact page.
- The provided generator script is pre-filled with the paths you shared.

## 포함된 변경사항 (KO)
- `mushra` page `content`를 HTML 블록으로 렌더링하도록 수정 (이미지/레이아웃용)
- 이미지/프롬프트 패널용 CSS 추가
- 자동 config 생성 스크립트 추가: `scripts/build_text2rir_but_mushra.py` (기본 30-trial random, Google Form mirror 전송 설정 포함)

## Included Changes (EN)
- `mushra` page `content` now renders as an HTML block (works with images/layouts)
- CSS for the image/prompt context panel
- Auto config generator script: `scripts/build_text2rir_but_mushra.py`

## 빠른 시작 (KO)
1. webMUSHRA 루트에서 스크립트를 실행합니다.
2. 생성된 config를 웹에서 엽니다.
3. `results/` 폴더에 결과가 저장되는지 확인합니다.

## Quick Start (EN)
1. Run the generator script from the webMUSHRA root.
2. Open the generated config in the browser.
3. Verify results are written to `results/`.

```bash
cd /home/kirak/webMUSHRA-master
python3 scripts/build_text2rir_but_mushra.py --num-trials 30 --seed 42
```

- 생성 config / Generated config:
  - `configs/generated/text2rir_but_mushra.yaml`
- trial 메타데이터 CSV / Trial metadata CSV:
  - `configs/generated/text2rir_but_mushra_trials.csv`

브라우저에서 열기 / Open in browser:

```text
http://localhost/webMUSHRA-master/index.html?config=generated/text2rir_but_mushra.yaml
```

서버 경로는 환경에 맞게 바꾸세요.  
Replace the host/path with your local server path.

## 기본 조건 구성 (KO)
- `Participant Info` 페이지에서 시작 시 `Age / Gender`를 입력합니다.
- `Reference`: 기본값은 `GT RIR convolved speech` (최신 시스템의 GT) 입니다.
- 평가 조건(stimuli):
  - `HIDDEN_REF_GT` (최신 BUT GT, hidden reference)
  - `T2R_GEN` (최신 text-to-RIR GEN)
  - `B1_GEN` (Baseline #1)
  - `B2_GEN` (Baseline #2)
  - `ANCHOR_LP3500`

## Default Condition Layout (EN)
- A `Participant Info` page (Age / Gender) is shown before the trials.
- `Reference`: default is `GT RIR convolved speech` (latest-system GT).
- Rated conditions (stimuli):
  - `HIDDEN_REF_GT` (latest BUT GT, hidden reference)
  - `T2R_GEN` (latest text-to-RIR GEN)
  - `B1_GEN` (Baseline #1)
  - `B2_GEN` (Baseline #2)
  - `ANCHOR_LP3500`

## 주요 옵션 (KO)
- `--num-trials N`: trial 수 (기본 30)
- `--google-form-url`, `--google-form-entry-id`: Google Form mirror 전송
- `--contact-phone`: 종료 페이지 연락처 문구
- `--sample-mode random|head`: 샘플링 방식
- `--reference-mode dry|latest_gt`: reference 버튼 내용
- `--dry-ext flac|wav`: LibriSpeech 확장자
- `--show-condition-names`: 조건 이름 표시 (디버그용)
- `--show-waveform`: waveform 표시
- `--disable-looping`: loop 기능 끄기
- `--no-condition-randomize`: 조건 랜덤 순서 비활성화

## Key Options (EN)
- `--num-trials N`: number of trials (default 30)
- `--google-form-url`, `--google-form-entry-id`: Google Form mirror upload
- `--contact-phone`: phone number shown on the final page
- `--sample-mode random|head`: selection mode
- `--reference-mode dry|latest_gt`: what the Reference button plays
- `--dry-ext flac|wav`: LibriSpeech extension
- `--show-condition-names`: reveal condition names (debug only)
- `--show-waveform`: show waveform
- `--disable-looping`: disable looping controls
- `--no-condition-randomize`: disable randomized condition order

## 중요 주의사항 (KO)
- 기본 `Reference=latest_gt` 설정은 GT RIR convolved speech를 reference로 사용합니다.
- `Reference=dry`로 바꾸는 경우 MUSHRA의 "정답 reference" 용도와는 다릅니다.
  - 이 경우 reference는 음성 내용 확인용(dry speech)으로 쓰는 설정입니다.
- LibriSpeech는 기본적으로 `.flac`입니다.
  - 브라우저에서 FLAC 디코딩이 실패하면 WAV로 변환 후 `--dry-ext wav`로 다시 생성하세요.
- 스크립트는 외부 데이터 폴더를 webMUSHRA 루트 아래 `external_data/text2rir_but_mushra/`에 symlink로 연결합니다.
  - 웹서버가 symlink 접근을 허용해야 합니다.
- Google Form 전송은 `no-cors` 방식(브라우저에서 응답 검증 불가)으로 추가 전송됩니다.
  - 로컬 `service/write.php` 저장도 함께 유지하는 것을 권장합니다.
- Google Form 단일 문항에 전체 JSON을 넣을 때 응답 길이 제한에 걸릴 수 있습니다.
  - 실제 폼에서 몇 건 테스트 후 저장 여부를 확인하세요.
- Docker 사용 시에는 외부 경로가 컨테이너에 mount되지 않으면 동작하지 않습니다.

## Important Notes (EN)
- By default (`Reference=latest_gt`), the Reference button plays GT RIR-convolved speech.
- If you switch to `Reference=dry`, it is not the MUSHRA "ground-truth" room reference.
  - It is used as dry speech content reference.
- LibriSpeech is usually `.flac`.
  - If browser FLAC decoding fails, convert to WAV and regenerate with `--dry-ext wav`.
- The script creates symlinks under `external_data/text2rir_but_mushra/` to expose external audio/images.
  - Your web server must allow symlink access.
- Google Form upload is sent via `no-cors` (browser cannot verify the response).
  - Keeping local `service/write.php` storage as a backup is recommended.
- A single Google Form item may hit response-length limits if you store the full session JSON.
  - Test with a few submissions first.
- In Docker, this will fail unless those external paths are mounted into the container.

## 결과 파일 (KO)
- webMUSHRA 결과는 `results/<testId>/` 아래 저장됩니다.
- 생성된 trial CSV(`configs/generated/text2rir_but_mushra_trials.csv`)를 함께 보관하면 결과 해석/복원에 편합니다.

## Result Files (EN)
- webMUSHRA writes results under `results/<testId>/`.
- Keep the generated trial CSV (`configs/generated/text2rir_but_mushra_trials.csv`) for analysis/reconstruction.

## 다음 커스터마이즈 후보 (KO/EN)
- KO: trial 수/샘플링 규칙 고정 (예: speaker 균형 샘플링)
- EN: Fix trial sampling rules (e.g., speaker-balanced sampling)
- KO: 평가 문항을 "자연스러움" vs "프롬프트 일치도"로 분리 (2-pass)
- EN: Split evaluation into "naturalness" vs "prompt-match" (2-pass)
- KO: `Reference`를 GT convolved speech로 변경
- EN: Switch `Reference` to GT convolved speech
