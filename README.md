# MiSTer Ethernet Audio

NES and PlayStation core builds that send game audio over a direct Ethernet connection to a Windows PC. Picture and controller input stay on MiSTer. The PC plays the sound through a connected audio device.

Tested with a Sonos Roam SL paired to Windows over Bluetooth. NES captures mono; PlayStation captures stereo, both at 48 kHz / 16-bit.

## Files

- `builds/`: tested RBF files, checksums and upstream revisions.
- `cores/NES/` and `cores/PSX/`: modified source, including upstream license files. Old upstream release binaries are omitted.
- `patches/`: tracked changes against the listed upstream commits. The added `sys/audio_uart.sv` is included in each source tree.
- `runtime/`: MiSTer sender, supervisor and Windows receiver.
- `tests/`: decoder checks and captured RTL simulation streams.

## Setup

This is a snapshot of a working setup, not a general-purpose installer. It requires a DE10-Nano MiSTer, Python 3 on MiSTer and Windows, and a direct Ethernet connection using link-local addresses. Zaparoo launch overrides were tested on Core 2.21.0.

1. Put `NES.rbf` and `PSX.rbf` in `/media/fat/_EthernetAudio/`. Keep the stock cores. Create an empty `.zaparooignore` file in that folder to keep it out of the media library.
2. Copy these runtime files to `/media/fat/Scripts/EthernetAudio/`: `protocol.py`, `send_audio.py`, `service.py`, `control.py`, `start.sh`, `Enable_Audio.sh`, `Disable_Audio.sh`, and `cores.json`.
3. Copy `protocol.py`, `play_audio.py` and `keep_audio.py` to a Windows folder, for example `$env:USERPROFILE\Documents\MiSTerEthernetAudio`. Create a virtual environment there and install the pinned packages from `requirements.txt`.
4. Generate a private shared token on Windows: `python -c "import secrets; print(secrets.token_hex(32))"`. Save it as `auth.token` beside the Windows scripts and copy the same file to the MiSTer service folder. Do not commit it.
5. Set the MiSTer link-local address in `service.py` and `keep_audio.py`. The current default is `169.254.93.225`. Set the WASAPI output name in `play_audio.py` if using something other than `Sonos Roam SL`. The sender accepts direct-link clients only and listens on TCP port 55241.
6. Add the following entries to the existing `/media/fat/zaparoo/config.toml`, preserving other settings. Replace an existing override for the same launcher rather than adding a second one.

```toml
[[launchers.default]]
launcher = "NES"
load_path = "_EthernetAudio/NES"

[[launchers.default]]
launcher = "PSX"
load_path = "_EthernetAudio/PSX"
```

Reload Zaparoo settings and refresh launchers, or restart MiSTer. Enable audio from **Scripts → EthernetAudio → Enable Audio**. On Windows, run `venv\Scripts\pythonw.exe keep_audio.py` from the receiver folder. The receiver reconnects when a supported game starts.

For MiSTer startup, add `sh /media/fat/Scripts/EthernetAudio/start.sh` to the existing `/media/fat/linux/user-startup.sh`, after its shebang. Preserve the rest of the file. For Windows startup, create a task at your user logon that runs the receiver's full `pythonw.exe` path with the full `keep_audio.py` path as its argument and the receiver folder as its working directory. Run it as the signed-in user, without elevation.

Use **Disable Audio** to stop the MiSTer sender. Create `stop.flag` in the Windows receiver folder to stop that process; remove it before starting again. To return to stock cores, remove the two Zaparoo launch overrides and reload its launchers.

## What was tested

- Audible sound in two NES games launched through the normal Zaparoo library.
- Audible sound in Spider-Man 2: Enter Electro and another PlayStation game, with normal game switching.
- Direct monitor output and wired controller input during playback.
- Both builds passed their reported clock timing checks without relaxing constraints. Inherited unconstrained-I/O warnings remain.
- Windows startup-task action and duplicate-instance protection were checked. A full Windows reboot/login cycle has not been verified.

Bluetooth adds delay. It was acceptable in the listening test; complete acoustic latency was not measured. Receiver logs recorded buffering underruns and dropped audio during some sessions. This is not a lossless or zero-latency link.

The PC and its audio device must remain on. Other cores are not supported by these builds. Automatic upstream core updates do not update these modified files.

## Building

Open `cores/NES/NES.qpf` or `cores/PSX/PSX.qpf` in Quartus Prime Lite 17.0.2 Build 602, with Cyclone V device support installed, or run `quartus_sh --flow compile NES` / `quartus_sh --flow compile PSX` from the respective project folder. Both projects use fitter seed 2. Output files are generated in `output_files/`.

The capture logic copies final mixed audio to the internal HPS UART1 connection. Linux reads the framed PCM stream and sends it over TCP. Each packet has a sequence number and CRC32. The Windows receiver uses a bounded playback buffer. No video or controller traffic is forwarded.

Each additional core needs checks for UART conflicts, available FPGA resources, timing and actual gameplay. The PSX build uses about 98% of the FPGA's ALMs; the initial buffer implementation did not fit.

Run the packaged decoder checks with `python -m unittest discover -s tests -v`.

## Credits and licenses

Based on [NES_MiSTer](https://github.com/MiSTer-devel/NES_MiSTer) and [PSX_MiSTer](https://github.com/MiSTer-devel/PSX_MiSTer). Exact revisions are in `builds/manifest.json`. Their source notices and licenses remain in the corresponding directories: NES GPLv3 and PSX GPLv2, with individual file notices retained.

Changes within each core follow that core's license. Standalone runtime scripts and tests are covered by the MIT license in `LICENSE`. No games, console BIOS files or credentials are included.
