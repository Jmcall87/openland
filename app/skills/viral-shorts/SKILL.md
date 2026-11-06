---
name: viral-shorts
description: Turn the user's clips into a viral 9:16 short in the style they describe, using shorts_edit (real ffmpeg + Whisper on the phone).
---
# Viral shorts workflow

1. **Get the inputs.** You need video paths in the computer (uploads land in /root/OpenLand/uploads). If the user hasn't given any, ask them to add clips in Studio → Shorts, or run_shell `ls -t /root/OpenLand/uploads`.
2. **Pick the style.** Map their words onto a preset and put the rest in `style_notes`:
   - "Hormozi", "business", "educational" → `hormozi`
   - "MrBeast", "hype", "challenge" → `mrbeast`
   - "fast", "TikTok edit", "high energy" → `fast`
   - "podcast", "interview" → `podcast`
   - "movie", "aesthetic", "film" → `cinematic`
   - "clean", "simple" → `minimal`
   - Colors ("green captions"), "more zooms", "no zooms", "one word", "lowercase" and "black and white" all work in style_notes.
3. **Write the hook.** Use the hooks-and-retention skill: 3–7 words, curiosity or a bold claim, never the channel name.
4. **Music (optional).** Use `stock_search` kind=audio with a mood query, then `stock_import`. Pass the path as `music`; it ducks under speech automatically. Tell the user the license and creator.
5. **Run `shorts_edit`** with `inputs` in story order, `max_seconds` (default 60; 30–45 works best for retention).
6. **Report honestly.** Give the path, duration, caption-word count and silences removed. Offer `exportToPhone` via Studio → Save to phone. If captions failed, say so.
7. **Iterate.** "More zooms" means rerun with `style_notes:"more zoom"`. "Shorter" means a lower `max_seconds`.

Pacing rules: no dead air over 0.4 s, a visual change every 1.5–3 s, a payoff within 45 s, and an ending that loops into the start.
