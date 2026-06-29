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
    openai_script_model: str = "gpt-4o"
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
    image_style: str = "modern, cinematic, vibrant digital art with a clean premium feel"
    image_overlay_text: bool = True  # overlay crisp brand+title on the AI image

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

    # --- Video assembly (M3) — ffmpeg static image + audio -> mp4. ---
    video_fps: int = 24
    video_crf: int = 20  # quality (lower = better/larger)
    video_audio_bitrate: str = "192k"

    # --- MongoDB Atlas ---
    mongodb_uri: str
    mongodb_db: str = "sarvo_podcast"

    # --- Brand / niche (swappable config, never hardcoded in logic) ---
    channel_brand_name: str = "Sarvo Podcast"
    default_hosts: list[str] = ["Anna", "Jake"]
    default_privacy: str = "unlisted"  # keep unlisted until pipeline is trusted

    # --- YouTube OAuth (desktop app) ---
    youtube_client_secret_file: str = "client_secret.json"
    youtube_token_file: str = "token.json"


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so settings are parsed exactly once per process."""
    return Settings()
