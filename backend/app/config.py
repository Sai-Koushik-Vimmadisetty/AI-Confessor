"""Environment-driven configuration. No secrets are hardcoded anywhere."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM provider selection: "anthropic" | "openai" | "mock".
    # Empty/unrecognized -> auto-select: anthropic if ANTHROPIC_API_KEY is set,
    # else openai if OPENAI_API_KEY is set, else mock (no key needed).
    # Adding a new provider = implement LLMClient in llm.py and register it here.
    llm_provider: str = ""

    # Anthropic (Claude)
    anthropic_api_key: str | None = None
    # Family alias that tracks the latest Sonnet snapshot; override via env if needed.
    anthropic_model: str = "claude-sonnet-4-6"

    # OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    openai_base_url: str | None = None  # override for proxies / Azure OpenAI compat endpoints

    # Vosk speech-to-text
    vosk_model_name: str = "vosk-model-small-en-us-0.15"
    vosk_model_dir: str = "/app/models"  # mounted as a docker volume so it persists
    stt_sample_rate: int = 16000  # Hz, 16-bit mono PCM expected from clients

    # Text-to-speech (Microsoft Edge TTS — free, no API key required)
    tts_enabled: bool = True
    tts_voice: str = "en-US-AriaNeural"

    # Conversation
    max_history_messages: int = 20  # sliding window of recent messages sent to the LLM
    system_prompt: str = (
        "You are the AI Confessor, a warm, non-judgmental conversational companion. "
        "People tell you what's on their mind and you respond with empathy, gentle humor, "
        "and thoughtful perspective. Keep replies concise and conversational — "
        "this is spoken dialogue, not an essay. Your replies are spoken aloud "
        "to the listener, so never claim you are text-only or unable to talk. "
        "Never claim to be human."
    )

    host: str = "0.0.0.0"
    port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def resolved_provider(self) -> str:
        """Effective LLM provider after key availability is considered."""
        want = (self.llm_provider or "").strip().lower()
        if want == "anthropic":
            return "anthropic" if self.anthropic_api_key else "mock"
        if want == "openai":
            return "openai" if self.openai_api_key else "mock"
        if want == "mock":
            return "mock"
        # Anything else (including unset) -> auto-select by key availability.
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        return "mock"

    @property
    def resolved_model(self) -> str:
        """Model ID for the effective provider (what /health and /api/config report)."""
        if self.resolved_provider == "anthropic":
            return self.anthropic_model
        if self.resolved_provider == "openai":
            return self.openai_model
        return "mock"  # no live model in mock mode — don't imply otherwise

    @property
    def mock_mode(self) -> bool:
        """True when no API key is configured — the app runs end-to-end with canned replies."""
        return self.resolved_provider == "mock"


settings = Settings()
