# path: backend/api/routes_asr.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, Field, ConfigDict

router = APIRouter()


class Span(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_ms: int = Field(..., ge=0, description="Start time of span in milliseconds")
    end_ms: int = Field(..., ge=0, description="End time of span in milliseconds")
    text_start: int = Field(..., ge=0, description="Start character offset in final text")
    text_end: int = Field(..., ge=0, description="End character offset (exclusive) in final text")


class AsrSegmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audio_b64: Optional[str] = Field(
        None, description="Base64-encoded audio (PCM16 WAV/MP3/OGG). Alternative to file upload."
    )
    sample_rate: Optional[int] = Field(
        None, description="If raw PCM provided, sample rate in Hz."
    )


class AsrSegmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    spans: List[Span]


def _decode_with_service(audio_bytes: bytes) -> AsrSegmentResponse:
    """
    Try to use the real ASR service if available; otherwise return a deterministic stub.
    """
    try:
        from ..services.asr_service import ASRService  # type: ignore
    except Exception:
        # Deterministic offline stub (no model dependency). Returns one span covering the full text.
        text = "[ASR STUB] audio_segment_" + datetime.utcnow().strftime("%H%M%S")
        return AsrSegmentResponse(
            text=text,
            spans=[Span(start_ms=0, end_ms=20000, text_start=0, text_end=len(text))],
        )
    svc = ASRService.instance()
    out = svc.decode_segment(audio_bytes)  # expected to return dict with text and spans
    return AsrSegmentResponse.model_validate(out)


@router.post(
    "/asr/segment",
    response_model=AsrSegmentResponse,
    response_class=ORJSONResponse,
    summary="Transcribe an audio segment into text with spans",
)
async def asr_segment(
    payload: Optional[AsrSegmentRequest] = Body(None),
    audio: Optional[UploadFile] = File(None, description="Audio file upload as alternative to JSON base64"),
):
    """
    Offline-first ASR endpoint.
    Accepts either:
      * JSON body with `audio_b64` (base64-encoded audio)
      * multipart/form-data file field `audio` (UploadFile)

    Returns normalized text and an array of spans with ms+char offsets.
    """
    audio_bytes: Optional[bytes] = None

    if audio is not None:
        audio_bytes = await audio.read()
    elif payload and payload.audio_b64:
        import base64

        try:
            audio_bytes = base64.b64decode(payload.audio_b64, validate=True)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 audio: {e}") from e

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="No audio provided (use 'audio' file or 'audio_b64').")

    try:
        return _decode_with_service(audio_bytes)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ASR processing failed: {e}") from e
