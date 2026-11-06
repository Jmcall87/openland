---
name: ai-shot-prompts
description: Write strong prompts for free open image (Pollinations) and video (LTX-Video) generators.
---
# Prompting for shots

Image prompt structure: subject + action, setting, lighting, lens or framing, style, mood. For example: "a lone astronaut walking through a neon Tokyo alley, rain, reflections, low angle, 35mm, cinematic lighting, teal and orange".

Video (LTX-Video) prompt: describe **one** continuous motion plus the camera. For example: "slow dolly-in on a barista pouring latte art, steam rising, warm morning light, shallow depth of field". Keep it 1–8 s and avoid scene changes or text in frame.

Aspect: 9:16 for shorts (768×1344 image, 512×704 video), 16:9 for movies.

Be honest. When `media_video` returns `ai:false`, it was a fallback (AI image + camera motion), so tell the user that.

Local models (local_media_model) are slower. SD-Turbo needs 4 steps, SD 1.5 needs 20, Z-Image Turbo needs 8, FLUX schnell needs 4, and Wan 2.1 video is very slow on phones.
