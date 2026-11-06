---
name: movie-editing
description: Build multi-track movies Higgsfield-style. Generate shots with camera moves, sequence them, add titles and music, grade, and render with movie_render.
---
# Movie editing (movie_render)

Project JSON:
```
{ "name": "Trailer", "width": 1920, "height": 1080, "fps": 30, "tracks": [
  { "kind": "video", "clips": [
    { "src": "/root/OpenLand/media/image-….jpg", "duration": 3, "motion": "push_in", "filter": "teal_orange", "transition": "fadeblack", "transitionDuration": 0.6 },
    { "src": "/root/OpenLand/media/video-….mp4", "in": 0, "duration": 4, "speed": 1, "filter": "film" } ] },
  { "kind": "overlay", "clips": [ { "src": "/root/OpenLand/stock/logo.png", "start": 0.5, "duration": 3, "scale": 0.25, "x": 0.85, "y": 0.1 } ] },
  { "kind": "text", "clips": [ { "text": "THIS SUMMER", "start": 0.3, "duration": 2.5, "size": 110, "y": 0.5, "animation": "rise" } ] },
  { "kind": "audio", "clips": [ { "src": "/root/OpenLand/stock/audio-….mp3", "start": 0, "duration": 12, "volume": 0.6, "fadeIn": 0.5, "fadeOut": 2 } ] } ] }
```

Workflow:
1. Write a shot list (5–12 shots) with a camera move per shot.
2. Make each shot. Use `media_video` for motion-heavy shots (LTX-Video). For stills, use `media_image` and then a camera `motion` on the clip: push_in, pull_out, pan_left/right, tilt_up/down, crash_zoom, dolly_zoom, orbit, handheld.
3. Main-track clips play back to back. A transition sits on the clip *before* the cut.
4. Grade with `filter`: none, warm, cool, vivid, teal_orange, film, vintage, fade, drama, bw. You can also use `adjust`: {brightness, contrast, saturation}.
5. Add titles on the text track and CC music from `stock_search` (credit it).
6. Render `preview: true` first (fast, low-res), then the full render. Report the path and duration.

Keep shots 2–4 s for trailers and 4–8 s for story. Match cuts on motion direction.
