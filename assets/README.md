# Assets

## `background.png` — the fixed video background

This image is used as the **talking-scene background of EVERY video** (the part
shown while the hosts speak, with captions and the waveform on top).

- **Size:** 1920 x 1080 (16:9). Other sizes are auto-fitted (center-cropped), but
  1920x1080 gives you pixel-perfect control.
- **Format:** PNG preferred (JPG also works — rename it to `background.png` or
  update `BACKGROUND_IMAGE_FILE` in `.env`).
- **Design rules** (because things are drawn on top of it):
  - keep the **upper-middle empty** → captions appear there
  - keep the **bottom-center strip empty** → the animated waveform sits there
  - put characters/decor on the left/right sides
- **To change the look:** just replace this file. No restart needed.
- **To go back to AI-generated backgrounds:** delete/rename this file.

The **thumbnail** (topic title card shown at the start of the video and used on
YouTube) is still AI-generated fresh for every episode.
