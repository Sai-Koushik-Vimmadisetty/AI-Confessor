"""Environment-driven configuration. No secrets are hardcoded anywhere."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM provider selection. "openai" is the only live provider today;
    # adding a new provider = implement LLMClient in llm.py and register it here.
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    openai_api_key: str | None = None
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
        "this is spoken dialogue, not an essay. Never claim to be human."
    )

    host: str = "0.0.0.0"
    port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def mock_mode(self) -> bool:
        """True when no API key is configured — the app runs end-to-end with canned replies."""
        return not self.openai_api_key


settings = Settings()
