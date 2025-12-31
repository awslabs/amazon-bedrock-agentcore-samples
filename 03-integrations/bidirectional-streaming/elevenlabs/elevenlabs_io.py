"""Audio I/O for bidirectional agent with WebSocket support.

Uses Nova Sonic for audio input (speech-to-text) and ElevenLabs for
text-to-speech output. Nova Sonic's audio output is discarded in favor
of ElevenLabs TTS for better voice quality.
"""

import asyncio
import base64
import logging
from typing import TYPE_CHECKING, Any, cast

from elevenlabs.client import AsyncElevenLabs
from strands.experimental.bidi.types.events import (
    AudioChannel,
    AudioSampleRate,
    BidiAudioInputEvent,
    BidiAudioStreamEvent,
    BidiOutputEvent,
    BidiInputEvent,
    BidiTextInputEvent,
    BidiTranscriptStreamEvent,
)
from strands.experimental.bidi.types.io import BidiInput, BidiOutput


if TYPE_CHECKING:
    from strands.experimental.bidi.agent.agent import BidiAgent

logger = logging.getLogger(__name__)


class NovaSonicAudioInput(BidiInput):
    """Handle audio input from React frontend for Nova Sonic.

    Receives audio from WebSocket and passes it to Nova Sonic for native STT.
    """

    def __init__(
        self,
        audio_queue: asyncio.Queue[BidiInputEvent],
    ):
        """Initialize Nova Sonic audio input.

        Args:
            audio_queue: Queue receiving audio data from WebSocket
        """
        self._audio_queue = audio_queue
        self._channels = 1
        self._rate = 16000
        self._format = "pcm"

    async def start(self, agent: "BidiAgent") -> None:
        """Initialize audio input.

        Args:
            agent: The BidiAgent instance
        """
        logger.debug("starting nova sonic audio input")

    async def stop(self) -> None:
        """Clean up audio input."""
        logger.debug("stopping nova sonic audio input")

    async def __call__(self) -> BidiInputEvent:
        """Read audio from queue and pass to Nova Sonic.

        Returns audio as BidiAudioInputEvent for Nova Sonic to process.
        """
        # Get audio chunk from WebSocket queue
        data = await self._audio_queue.get()

        # Convert to base64 for Nova Sonic

        logger.debug("nova_sonic_input")

        return data


class ElevenLabsAudioOutput(BidiOutput):
    """Handle audio output to React frontend with ElevenLabs TTS.

    Converts text responses to speech using ElevenLabs and sends audio
    to the WebSocket client. Discards any audio output from Nova Sonic.
    """

    def __init__(
        self,
        websocket_send: Any,
        api_key: str,
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",  # Rachel voice
        model: str = "eleven_multilingual_v2",
    ):
        """Initialize ElevenLabs audio output.

        Args:
            websocket_send: WebSocket send function
            api_key: ElevenLabs API key
            voice_id: ElevenLabs voice ID to use
            model: ElevenLabs TTS model to use
        """
        self._websocket_send = websocket_send
        self._api_key = api_key
        self._voice_id = voice_id
        self._model = model
        self._client: AsyncElevenLabs | None = None
        self.interrupt = False
        self.playing = False

    async def start(self, agent: "BidiAgent") -> None:
        """Initialize ElevenLabs client.

        Args:
            agent: The BidiAgent instance
        """
        logger.debug("starting elevenlabs audio output")
        self._client = AsyncElevenLabs(api_key=self._api_key)
        logger.debug("elevenlabs audio output started")

    async def stop(self) -> None:
        """Clean up ElevenLabs client."""
        logger.debug("stopping elevenlabs audio output")
        # AsyncElevenLabs doesn't need explicit cleanup
        self._client = None
        logger.debug("elevenlabs audio output stopped")

    async def __call__(self, event: BidiOutputEvent) -> None:
        """Process agent output and convert text to speech.

        Args:
            event: Output event from the agent
        """

        # Handle transcript events - convert text to speech with ElevenLabs
        if event.get("type", "") == "bidi_transcript_stream":
            logger.info(event)
            text = event.get("text", "")
            if event.get("role", "") == "user" and self.playing:
                self.interrupt = True
                return
            if (
                text
                and self._client
                and event.get("role", "") == "assistant"
                and not event.get("is_final", True)
            ):
                logger.info("text_length=<%d> | converting text to speech", len(text))
                try:
                    # Generate audio using ElevenLabs TTS (returns AsyncIterator)
                    audio_generator = self._client.text_to_speech.convert(
                        voice_id=self._voice_id,
                        text=text,
                        model_id=self._model,
                        output_format="pcm_16000",
                    )

                    # Stream audio chunks to WebSocket
                    cnt = 0
                    await self._websocket_send(event)
                    self.playing = True
                    async for audio_chunk in audio_generator:
                        if self.interrupt:
                            self.interrupt = False
                            break
                        audio_b64 = base64.b64encode(audio_chunk).decode("utf8")

                        await self._websocket_send(
                            {
                                "type": "bidi_audio_stream",
                                "audio": audio_b64,
                                "format": "pcm",
                                "sample_rate": 16000,
                                "channels": 1,
                            }
                        )
                        logger.info(
                            "audio_bytes=<%d> | sent <%d> audio chunk to websocket",
                            len(audio_chunk),
                            cnt,
                        )
                        cnt = cnt + 1
                    self.playing = False
                    return

                except Exception as e:
                    logger.error("error=<%s> | failed to generate speech", str(e))
                    return

        # Discard audio stream events from Nova Sonic (we use ElevenLabs instead)
        elif event.get("type", "") == "bidi_audio_stream":
            logger.debug("discarding nova sonic audio output (using elevenlabs tts)")
            # await self._websocket_send(event)
            return
        # Forward all events as JSON for frontend display
        await self._websocket_send(event)


class NovaElevenLabsIO:
    """Combined Nova Sonic input + ElevenLabs output for bidirectional agent."""

    def __init__(
        self,
        audio_queue: asyncio.Queue[BidiInputEvent],
        websocket_send: Any,
        api_key: str,
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",
        tts_model: str = "eleven_multilingual_v2",
    ):
        """Initialize Nova Sonic + ElevenLabs I/O.

        Args:
            audio_queue: Queue for receiving audio from WebSocket
            websocket_send: Function to send data to WebSocket
            api_key: ElevenLabs API key
            voice_id: Voice ID for TTS
            tts_model: Text-to-speech model
        """
        self._audio_queue = audio_queue
        self._websocket_send = websocket_send
        self._api_key = api_key
        self._voice_id = voice_id
        self._tts_model = tts_model

    def input(self) -> NovaSonicAudioInput:
        """Return audio input handler for Nova Sonic."""
        return NovaSonicAudioInput(
            audio_queue=self._audio_queue,
        )

    def output(self) -> ElevenLabsAudioOutput:
        """Return audio output handler for ElevenLabs TTS."""
        return ElevenLabsAudioOutput(
            websocket_send=self._websocket_send,
            api_key=self._api_key,
            voice_id=self._voice_id,
            model=self._tts_model,
        )
