"""Central application settings, loaded once from `.env` via pydantic-settings.

Everything niche-specific (brand, hosts, voices, topic) lives here as config so the
SAME pipeline can be repointed to any niche later without touching module logic.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "Sarvo Podcast Pipeline"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # --- CORS ---
    cors_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    # --- OpenAI ---
    openai_api_key: str
    openai_script_model: str = "gpt-5.5"
    openai_tts_model: str = "gpt-4o-mini-tts"  # most steerable TTS via `instructions`
    tts_voice_host1: str = "coral"  # warm, expressive female (host 1 / Anna)
    tts_voice_host2: str = "ash"  # expressive, easygoing male (host 2 / Jake)

    # --- Script generation (the "show profile" = swappable niche/voice) ---
    # Change these to repoint the SAME pipeline to any niche (finance, tech, ...).
    script_temperature: float = 0.8
    default_duration_minutes: float = 10.0  # used when the request omits a duration
    words_per_minute: int = 150  # spoken pace; target_words = minutes * this
    show_language: str = "simple, easy, everyday English a beginner can follow"
    show_tone: str = "warm and genuinely valuable, with light, natural humor"

    def words_for_minutes(self, minutes: float) -> int:
        return round(minutes * self.words_per_minute)

    # --- TTS / audio (M2) — the quality gate. Provider is swappable. ---
    tts_provider: str = "openai"  # "openai" | "elevenlabs" (interface-based)
    tts_format: str = "mp3"
    tts_concurrency: int = 5  # parallel synthesis calls (order preserved)
    tts_pause_same_ms: int = 220  # gap when the same host keeps talking
    tts_pause_turn_ms: int = 380  # gap when the conversation hands to the other host
    tts_target_dbfs: float = -16.0  # loudness-normalize the final mix
    tts_cost_per_minute: float = 0.015  # approx gpt-4o-mini-tts; update if pricing changes
    media_dir: str = "media"
    # The overall delivery direction lives in prompts/tts_delivery.txt (editable).
    # Per-host flavor so the two voices feel like distinct people (swappable):
    tts_persona_host1: str = "Bright, friendly and warm; a touch upbeat and curious."
    tts_persona_host2: str = "Calm and easygoing; a touch lower, laid-back, with dry light humor."

    # --- Image (M3) — AI background (gpt-image-1) + branded text overlay. ---
    image_provider: str = "openai"  # "openai" (AI) | "pillow" (free solid card)
    openai_image_model: str = "gpt-image-1"  # best; auto-falls back to dall-e-3
    image_quality: str = "medium"  # gpt-image-1: low|medium|high|auto
    image_style: str = (
        "clean flat vector illustration, modern editorial style, bold shapes, "
        "warm friendly colors on the characters, premium and minimal"
    )
    image_overlay_text: bool = True  # overlay crisp brand+title on the thumbnail variant
    # Fixed background: if this file exists, EVERY video uses it as the talking-scene
    # background (no AI cost). Replace the file to change the look; delete it to go
    # back to AI-generated backgrounds. Recommended: 1920x1080 PNG.
    background_image_file: str = "assets/background.png"

    image_width: int = 1920
    image_height: int = 1080
    image_bg_color: str = "#0F172A"  # used by the pillow fallback / behind overlay
    image_accent_color: str = "#F59E0B"  # amber
    image_title_color: str = "#FFFFFF"
    image_subtitle_color: str = "#CBD5E1"  # light slate
    image_scrim_opacity: int = 110  # 0-255 dark wash over AI image for text readability
    # Fonts: first existing path wins; falls back to a built-in if none found.
    image_font_bold: str = "C:/Windows/Fonts/arialbd.ttf"
    image_font_regular: str = "C:/Windows/Fonts/arial.ttf"

    # --- Video assembly (M3) — ffmpeg image + audio (+captions +waveform) -> mp4. ---
    video_fps: int = 24
    video_crf: int = 20  # quality (lower = better/larger)
    video_audio_bitrate: str = "192k"

    # Intro card: show the topic thumbnail SILENTLY at the start, then the talking
    # scene begins and audio/captions/waveform all start together. 0 disables.
    video_intro_seconds: float = 2.0

    # Thumbnail title overlay (topic text in the empty TOP-CENTER of the design).
    thumbnail_title_font: str = "C:/Windows/Fonts/impact.ttf"  # classic thumbnail font
    thumbnail_title_font_size: int = 150  # customizable; auto-shrinks if too long
    thumbnail_title_uppercase: bool = True  # DREAMS & GOALS style
    thumbnail_title_shorten: bool = True  # drop '| Learn English Fast'-style tails
    thumbnail_title_width_ratio: float = 0.52  # text stays in the center column
    thumbnail_title_margin_top: int = 56  # px from the top edge
    # Colors auto-switch with the artwork's brightness; accent = the pop line.
    thumbnail_text_on_light: str = "#1E293B"  # dark slate on bright art
    thumbnail_accent_on_light: str = "#DC2626"  # strong red
    thumbnail_text_on_dark: str = "#FFFFFF"
    thumbnail_accent_on_dark: str = "#FBBF24"  # warm amber
    # Brand mark drawn on the background's TOP-LEFT corner.
    background_brand_text: str = "SARVO"

    # Animated audio waveform (bottom center, like pro podcast channels).
    video_waveform: bool = True
    waveform_width: int = 840
    waveform_height: int = 130
    waveform_margin_bottom: int = 140  # px from the bottom edge
    waveform_color: str = "white"

    # Burned-in live captions (what the hosts are saying, phrase by phrase).
    video_captions: bool = True
    caption_font: str = "Arial"
    caption_font_size: int = 62
    caption_margin_top: int = 200  # px from the top edge (kept clear in the AI image)
    caption_host1_color: str = "&H00FFFFFF"  # ASS &HAABBGGRR — white
    caption_host2_color: str = "&H00BFD42D"  # teal (#2DD4BF)
    caption_max_words: int = 5  # words shown per caption chunk

    # --- MongoDB Atlas ---
    mongodb_uri: str
    mongodb_db: str = "sarvo_podcast"

    # --- Brand / niche (swappable config, never hardcoded in logic) ---
    channel_brand_name: str = "Sarvo Podcast"
    default_hosts: list[str] = ["Jd", "Sarvo"]
    default_privacy: str = "unlisted"  # keep unlisted until pipeline is trusted

    # --- YouTube OAuth (desktop app) ---
    youtube_client_secret_file: str = "client_secret.json"
    youtube_token_file: str = "token.json"
    youtube_category_id: str = "28"  # 28 = Science & Technology
    youtube_made_for_kids: bool = False


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so settings are parsed exactly once per process."""
    return Settings()
