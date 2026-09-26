# NEXUS Studio Engine v1.0

Clean rebuild of the video-generation engine.

## Architecture

1. AI Director — understands the narration and creates a semantic storyboard.
2. Visual Provider — generates scene-specific 16:9 visuals.
3. Renderer — animates each visual, concatenates scenes and synchronizes narration.
4. Web App — accepts narration audio + script and exposes the generated MP4.

## AI provider

The current prototype uses Google Gemini through the official google-genai SDK.

Environment variable:
GEMINI_API_KEY

Optional model overrides:
NEXUS_TEXT_MODEL=gemini-3.8-flash
NEXUS_IMAGE_MODEL=gemini-3.1-flash-image

If the API key is absent, visual generation stops with a clear configuration error instead of silently generating meaningless placeholder graphics.

## Prototype goal

The first target is a 20–30 second educational video with 4–5 semantically connected scenes.

The architecture deliberately avoids the old renderer's generic circles, nodes, particles, decorative lines, arbitrary zooms and keyword-only scene classification.

The AI Director decides what the viewer should see before the image model is called.

## Render

The Docker container starts:
python NEXUS_Studio_Engine_v1_0/app.py

Render should point to the repository's main branch with automatic deploy enabled.
