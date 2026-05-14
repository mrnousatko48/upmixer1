# Upmix Pro (X-Bass Edition)

A high-fidelity 5.1 audio upmixer for Linux (PipeWire).

## Features
- **Ultra Bass Engine**: Powered by LADSPA CAPS Saturator and Compressor for chest-hitting bass.
- **Stereo Widening**: Advanced Mid-Side processing for a massive soundstage.
- **Portability**: One-click installation from the UI.
- **Real-time Control**: Adjust rear fill, center clarity, and sub-alignment on the fly.

## "Download & Go" Setup

1. **Install Dependencies**:
   Ensure you have PipeWire and the CAPS LADSPA plugins installed.
   ```bash
   # On Bazzite / Fedora:
   sudo dnf install pipewire-utils ladspa-caps-plugins
   ```

2. **Run the App**:
   ```bash
   python3 upmix_app.py
   ```

3. **Install the Sink**:
   Click the **"Install Sink"** button at the top of the app. This will:
   - Create the necessary PipeWire configuration.
   - Restart PipeWire to activate the `Upmix_Sink`.

4. **Enjoy**:
   The app will automatically route stereo streams to the new upmixer.

## Manual Troubleshooting
If you don't hear anything, ensure your hardware is set to "5.1 Surround" mode in your system audio settings. The upmixer expects a 6-channel hardware output.




i couldnt find anything to fit my needs so i "made" this (w antigravity...) feel free to use it. hope it helps :)