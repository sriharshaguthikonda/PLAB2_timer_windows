# PLAB2 Timer (Windows desktop, Python/PyQt5)

This repository is the **Windows desktop** implementation of the PLAB2 timer, built with Python, PyQt5, gTTS, and pygame. It is distinct from any other "plaptimer" projects (e.g., web/mobile variants).

## Features
- Adjustable total exam duration with minute/second controls.
- Timeline scrubber with coarse (1m) and fine (10s) adjustment.
- Configurable alert points (enter room, sleep, auto 2-min remaining, end).
- Text-to-speech audio alerts (gTTS) with multiple voice presets and volume control.
- Dark UI theme styled after VS Code.

## Requirements
- Python 3.10+ (tested on Windows).
- Virtual environment recommended (per-project):
  ```pwsh
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```
- Install dependencies:
  ```pwsh
  pip install PyQt5 pygame gTTS
  ```

## Running
```pwsh
python PLAB2_Exam_timer_qt.py
```

## Notes
- This is the desktop/Windows Python version; use this repo when you need the PyQt5/gTTS build.
- Avoid mixing with other similarly named timers to keep artifacts separate.
