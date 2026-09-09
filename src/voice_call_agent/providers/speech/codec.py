import math
import struct

# Precomputed ITU-T G.711 mu-law decompression lookup table (256 entries)
MULAW_TO_PCM16_TABLE: list[int] = []
for _i in range(256):
    _byte = ~_i & 0xFF
    _sign = -1 if (_byte & 0x80) else 1
    _exponent = (_byte >> 4) & 0x07
    _mantissa = _byte & 0x0F
    _sample = (_mantissa << 3) + 0x84
    _sample <<= _exponent
    _sample -= 0x84
    MULAW_TO_PCM16_TABLE.append(_sign * _sample)


def mulaw_to_pcm16(mulaw_bytes: bytes) -> bytes:
    """Decode 8-bit ITU-T G.711 mu-law audio into 16-bit signed linear PCM bytes."""
    samples = [MULAW_TO_PCM16_TABLE[b] for b in mulaw_bytes]
    return struct.pack(f"<{len(samples)}h", *samples)


def _pcm_sample_to_mulaw(sample: int) -> int:
    """Encode a single 16-bit signed PCM sample into 8-bit mu-law."""
    sign = 0x80 if sample < 0 else 0x00
    if sample < 0:
        sample = -sample

    sample += 0x84
    sample = min(sample, 0x7FFF)

    exponent = 7
    thresholds = (0x100, 0x200, 0x400, 0x800, 0x1000, 0x2000, 0x4000)
    for exp, threshold in enumerate(thresholds):
        if sample < threshold:
            exponent = exp
            break

    mantissa = (sample >> (exponent + 3)) & 0x0F
    return ~(sign | (exponent << 4) | mantissa) & 0xFF


def pcm16_to_mulaw(pcm16_bytes: bytes) -> bytes:
    """Encode 16-bit signed linear PCM bytes into 8-bit ITU-T G.711 mu-law bytes."""
    num_samples = len(pcm16_bytes) // 2
    if num_samples == 0:
        return b""
    samples = struct.unpack(f"<{num_samples}h", pcm16_bytes[: num_samples * 2])
    return bytes(_pcm_sample_to_mulaw(s) for s in samples)


def create_wav(pcm16_bytes: bytes, sample_rate: int = 8000, channels: int = 1) -> bytes:
    """Wrap 16-bit linear PCM audio in a standard 44-byte RIFF/WAVE header."""
    data_size = len(pcm16_bytes)
    riff_chunk_size = 36 + data_size
    byte_rate = sample_rate * channels * 2
    block_align = channels * 2

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        riff_chunk_size,
        b"WAVE",
        b"fmt ",
        16,  # Subchunk1Size (16 for PCM)
        1,  # AudioFormat (1 for PCM)
        channels,
        sample_rate,
        byte_rate,
        block_align,
        16,  # BitsPerSample
        b"data",
        data_size,
    )
    return header + pcm16_bytes


def calculate_rms_energy(pcm16_bytes: bytes) -> float:
    """Calculate Root Mean Square (RMS) energy of 16-bit PCM audio.

    Returns a float from 0.0 to 32767.0.
    """
    num_samples = len(pcm16_bytes) // 2
    if num_samples == 0:
        return 0.0
    samples = struct.unpack(f"<{num_samples}h", pcm16_bytes[: num_samples * 2])
    sum_squares = sum(s * s for s in samples)
    return math.sqrt(sum_squares / num_samples)
