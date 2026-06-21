import asyncio
import re
from pathlib import Path
from shibaclaw.tts.base import BaseTTS

class SupertonicTTS(BaseTTS):
    name = "supertonic"
    display_name = "Supertonic Local TTS"

    def __init__(self, config: dict):
        super().__init__(config)
        self._tts = None

    def _lazy_init(self):
        if self._tts is None:
            from supertonic import TTS
            self._tts = TTS(auto_download=True)

    async def synthesize(self, text: str, output_path: Path) -> Path:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._sync_synthesize, text, output_path)
        return output_path

    def _sync_synthesize(self, text: str, output_path: Path):
        self._lazy_init()
        cleaned_text = self._clean_markdown(text)
        if not cleaned_text:
            cleaned_text = "Hello."
        
        voice_name = self.config.get("tts_voice", "F1")
        voice_lang = self.config.get("tts_lang", "en")
        style = self._tts.get_voice_style(voice_name=voice_name)
        wav, duration = self._tts.synthesize(cleaned_text, voice_style=style, lang=voice_lang)
        self._tts.save_audio(wav, str(output_path.absolute()))

    def _clean_markdown(self, text: str) -> str:
        clean = re.sub(r'```[\s\S]*?```', '', text)
        clean = re.sub(r'`[^`]*`', '', clean)
        clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean)
        clean = re.sub(r'[*_#]+', '', clean)
        clean = clean.encode('ascii', 'ignore').decode('ascii')
        return clean.strip()
