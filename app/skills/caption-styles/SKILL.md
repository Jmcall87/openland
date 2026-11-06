---
name: caption-styles
description: Caption looks for shorts (Hormozi, MrBeast, podcast, cinematic, minimal) and how to request them.
---
# Caption styles (shorts_edit)

| Style | Font | Words per line | Highlight | Notes |
|---|---|---|---|---|
| hormozi | Montserrat ExtraBold, UPPERCASE | 3 | yellow | thick outline, punch-in every 2.5 s |
| mrbeast | Anton, UPPERCASE | 2 | green | huge, saturated grade, zoom every 1.8 s |
| fast | Anton | 1 | brand orange | zoom every 1.2 s |
| podcast | Montserrat | 4 | soft orange | calm, gentle zooms |
| cinematic | Montserrat light | 5 | none | letterbox bars, film grade |
| minimal | Montserrat | 4 | none | clean, no zooms |

Tweaks go in `style_notes`: "green/yellow/red/blue/orange/pink captions", "one word", "lowercase", "more zoom", "no zoom", "black and white".
For standalone subtitles, use `media_captions` (whisper.cpp, on device) to get an .srt.
