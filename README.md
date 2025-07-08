# Auto Piano Player for Sky: Children of the Light

An **Auto Piano Player** that reads a JSON/text note file exported from Sky: Children of the Light and automatically “plays” the corresponding keys on your keyboard.

![screenshot of GUI](path/to/screenshot.png)

## Features

- 🖱️ **One‑click** EXE to run on Windows (no Python install required)  
- 🎹 GUI made with **Tkinter** for selecting files, playback controls (Play/Pause/Stop), speed and hold adjustment, and seek bar  
- 🔀 Supports multiple input formats (raw JSON export, text list, or wrapped in a `"songNotes"` object)  
- 🔒 Thread‑safe key presses with overlap handling  
- ⏱️ Precise timing with configurable speed multiplier and note‑hold duration  

## Getting Started

### Prerequisites

- Windows 10 or later (for the one‑click `.exe`)  
- **Python 3.8+** if running from source  
- Administrator privileges may be required for low‑level keyboard hooks

### Installation (from source)

1. **Clone the repo:**

   ```bash
   git clone https://github.com/Somansh1/auto-music-sky.git
   cd auto-music-sky
   ```
   
2. **Create and activate a virtual environment (recommended):**

```bash
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
```

3. **Install dependencies:**

```bash
pip install -r requirements.txt
```

4. **Run the GUI:**

```bash
python src/piano_player.py
```

### Usage

1. Click Browse... and select your exported notes file (.json or .txt).

2. Adjust Speed (e.g., 1.0 = normal, 2.0 = twice as fast).

3. Adjust Hold (s) for how long each key is held.

4. Use Play, Pause/Resume, Stop, and the seek bar to control playback.

### One‑Click EXE

We’ve also included a pre‑built .exe in the dist/ folder for Windows users—no Python install required. Simply double‑click auto-piano-player.exe.

### Contributing

1. Fork the repository.

2. Create a feature branch: git checkout -b my-feature.

3. Commit your changes: git commit -m "Add awesome feature".

4. Push to your branch: git push origin my-feature.

5. Open a Pull Request—bonus points for tests! 🧪

### License
This project is licensed under the MIT License. See LICENSE for details.


## 5. Putting Your Code in `src/piano_player.py`

Just move your long script into `src/piano_player.py`. At the top you may add a module docstring, e.g.:

```python
"""
Auto Piano Player
-----------------
Reads note data exported from Sky: Children of the Light and simulates key presses
to “play” the song automatically.

Usage:
    python piano_player.py
"""
```