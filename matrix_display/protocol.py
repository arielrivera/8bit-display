"""Protocol helpers for the Merkury / MI Matrix Display.

Protocol notes are based on public work by:
- https://github.com/offe/mi-led-display
- https://github.com/LostBeard/SpawnDev.MatrixLEDDisplay
"""

from __future__ import annotations

from collections.abc import Iterable

WIDTH = 16
HEIGHT = 16
PIXELS = WIDTH * HEIGHT
CHUNK_COUNT = 8
PIXELS_PER_CHUNK = 32
RGB_BYTES_PER_CHUNK = PIXELS_PER_CHUNK * 3


def checksum(data: Iterable[int]) -> int:
    """Return the device's one-byte additive checksum."""
    return sum(data) & 0xFF


def packet(message: bytes) -> bytes:
    """Wrap a command body in the display's 0xbc packet envelope."""
    full_len = len(message) + 13
    tail = bytes([checksum(message)])
    if full_len % 32 != 0:
        tail += b"\x55"
    return b"\xbc" + message + tail


POWER_OFF = packet(bytes([0xFF, 0x00]))
POWER_ON = packet(bytes([0xFF, 0x01]))
RESET = packet(bytes([0x00, 0x15]))
START_SLIDESHOW_MODE = packet(bytes([0x00, 0x12]))
CLEAR_GRAFFITI_MODE = packet(bytes([0x00, 0x0D]))
START_GRAFFITI_MODE = packet(bytes([0x00, 0x01]))
STATIC_IMAGE_WRITE_ENABLE = packet(bytes([0x00, 0x11, 0xF1]))
STATIC_IMAGE_WRITE_DISABLE = packet(bytes([0x00, 0x11, 0xF2]))
TEMP_IMAGE_WRITE_ENABLE = packet(bytes([0x0F, 0xF1, 0x08]))
TEMP_IMAGE_WRITE_DISABLE = packet(bytes([0x0F, 0xF2, 0x08]))
SLIDESHOW_MARKER = packet(bytes([0x02, 0x07, 0x3C]))


def temp_image_chunk(chunk_index: int, rgb: bytes) -> bytes:
    """Build one temporary-image chunk packet.

    The display expects eight chunks. Each chunk contains two display rows:
    32 pixels * RGB = 96 bytes.
    """
    if not 1 <= chunk_index <= CHUNK_COUNT:
        raise ValueError(f"chunk_index must be 1..{CHUNK_COUNT}")
    if len(rgb) != RGB_BYTES_PER_CHUNK:
        raise ValueError(f"rgb chunk must be {RGB_BYTES_PER_CHUNK} bytes")
    return packet(bytes([0x0F, chunk_index]) + rgb)


def slideshow_frame_chunk(frame_index: int, chunk_index: int, rgb: bytes) -> bytes:
    """Build one slideshow-frame chunk packet."""
    if not 1 <= frame_index <= CHUNK_COUNT:
        raise ValueError(f"frame_index must be 1..{CHUNK_COUNT}")
    if not 1 <= chunk_index <= CHUNK_COUNT:
        raise ValueError(f"chunk_index must be 1..{CHUNK_COUNT}")
    if len(rgb) != RGB_BYTES_PER_CHUNK:
        raise ValueError(f"rgb chunk must be {RGB_BYTES_PER_CHUNK} bytes")
    return packet(bytes([0x02, frame_index, chunk_index]) + rgb)


def gamma_correct(value: int, gamma: float = 0.6) -> int:
    """Apply the same gamma style used by the web implementation."""
    if not 0 <= value <= 255:
        raise ValueError("RGB values must be 0..255")
    corrected = (value / 255) ** (1 / gamma)
    return max(0, min(255, round(corrected * 255)))


def normalize_rgb_pixels(pixels: Iterable[tuple[int, int, int]], gamma: float = 0.6) -> list[tuple[int, int, int]]:
    normalized = [
        (gamma_correct(r, gamma), gamma_correct(g, gamma), gamma_correct(b, gamma))
        for r, g, b in pixels
    ]
    if len(normalized) != PIXELS:
        raise ValueError(f"expected {PIXELS} pixels for a {WIDTH}x{HEIGHT} image")
    return normalized


def image_packets(
    pixels: Iterable[tuple[int, int, int]],
    gamma: float = 0.6,
    save: bool = False,
) -> list[bytes]:
    """Return packets to display a 16x16 RGB image.

    The temporary sequence can be overridden by whatever the device is already
    playing. The saved sequence mirrors the app's save flow and makes the image
    stick by wrapping the temp image write in static-image write commands.
    """
    normalized = normalize_rgb_pixels(pixels, gamma=gamma)
    packets = [TEMP_IMAGE_WRITE_ENABLE]

    for chunk in range(CHUNK_COUNT):
        start = chunk * PIXELS_PER_CHUNK
        end = start + PIXELS_PER_CHUNK
        rgb = bytes(channel for pixel in normalized[start:end] for channel in pixel)
        packets.append(temp_image_chunk(chunk + 1, rgb))

    packets.append(TEMP_IMAGE_WRITE_DISABLE)
    if save:
        packets = [RESET, STATIC_IMAGE_WRITE_ENABLE] + packets + [STATIC_IMAGE_WRITE_DISABLE]
    return packets


def slideshow_packets(
    frames: Iterable[Iterable[tuple[int, int, int]]],
    gamma: float = 0.6,
    save: bool = False,
) -> list[bytes]:
    """Return packets that upload frames into the display's eight slideshow slots."""
    source_frames = [normalize_rgb_pixels(frame, gamma=gamma) for frame in frames]
    if not source_frames:
        raise ValueError("slideshow requires at least one frame")
    if len(source_frames) > CHUNK_COUNT:
        raise ValueError(f"slideshow supports at most {CHUNK_COUNT} frames")

    normalized_frames = [source_frames[index % len(source_frames)] for index in range(CHUNK_COUNT)]
    frame_count = CHUNK_COUNT
    packets: list[bytes] = []
    if save:
        packets.extend([RESET, STATIC_IMAGE_WRITE_ENABLE])
    packets.append(START_SLIDESHOW_MODE)

    for frame_index, pixels in enumerate(normalized_frames, start=1):
        packets.append(packet(bytes([0x02, 0xF1, frame_count])))
        for chunk in range(CHUNK_COUNT):
            start = chunk * PIXELS_PER_CHUNK
            end = start + PIXELS_PER_CHUNK
            rgb = bytes(channel for pixel in pixels[start:end] for channel in pixel)
            packets.append(slideshow_frame_chunk(frame_index, chunk + 1, rgb))
        if save and frame_index == frame_count:
            packets.append(SLIDESHOW_MARKER)
        packets.append(packet(bytes([0x02, 0xF2, frame_count])))

    if save:
        packets.append(STATIC_IMAGE_WRITE_DISABLE)
    packets.append(START_SLIDESHOW_MODE)
    return packets


def gradient_pixels() -> list[tuple[int, int, int]]:
    """Generate a simple visible 16x16 RGB gradient test image."""
    pixels: list[tuple[int, int, int]] = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            pixels.append((x * 17, y * 17, ((x + y) // 2) * 17))
    return pixels


def solid_pixels(r: int, g: int, b: int) -> list[tuple[int, int, int]]:
    return [(r, g, b)] * PIXELS
