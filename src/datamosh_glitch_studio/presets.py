"""
Predefined glitch presets and profiles for datamosh-glitch-studio.
Zero external runtime dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GlitchPreset:
    """Glitch effect configuration preset."""
    id: str
    name: str
    description: str
    slice_height: int = 12
    horizontal_shift_max: int = 24
    vertical_block_width: int = 16
    vertical_shift_max: int = 18
    color_shift_x: int = 6
    color_shift_y: int = 4
    scanline_intensity: float = 0.35
    scanline_frequency: int = 4
    block_artifact_size: int = 16
    block_artifact_probability: float = 0.25
    bitflip_rate: float = 0.001
    ghost_blend: float = 0.4
    noise_intensity: float = 0.15


PRESETS: Dict[str, GlitchPreset] = {
    "h264_iframe_drop": GlitchPreset(
        id="h264_iframe_drop",
        name="H.264 I-Frame Drop (Classic Datamosh)",
        description="Simulates missing keyframe compression artifacts with motion vector smearing and macroblock drag.",
        slice_height=18,
        horizontal_shift_max=32,
        vertical_block_width=24,
        vertical_shift_max=22,
        color_shift_x=4,
        color_shift_y=2,
        block_artifact_size=32,
        block_artifact_probability=0.45,
        ghost_blend=0.65,
        scanline_intensity=0.1
    ),
    "cyberpunk_vcr": GlitchPreset(
        id="cyberpunk_vcr",
        name="Cyberpunk VCR Tracking Glitch",
        description="Magnetic tape tracking errors, heavy horizontal scanline rolls, and chromatic aberration.",
        slice_height=6,
        horizontal_shift_max=45,
        vertical_block_width=8,
        vertical_shift_max=10,
        color_shift_x=12,
        color_shift_y=3,
        scanline_intensity=0.65,
        scanline_frequency=2,
        noise_intensity=0.35,
        ghost_blend=0.25
    ),
    "rgb_split_overdrive": GlitchPreset(
        id="rgb_split_overdrive",
        name="RGB Chromatic Aberration Overdrive",
        description="Extreme color channel separation with decoupled spatial offsets.",
        slice_height=14,
        horizontal_shift_max=12,
        vertical_block_width=16,
        vertical_shift_max=8,
        color_shift_x=25,
        color_shift_y=16,
        scanline_intensity=0.2,
        ghost_blend=0.3
    ),
    "analog_tape_decay": GlitchPreset(
        id="analog_tape_decay",
        name="Analog Tape Decay & Static",
        description="Degraded magnetic tape with high noise floor, intermittent dropouts, and subtle sync loss.",
        slice_height=20,
        horizontal_shift_max=18,
        vertical_block_width=20,
        vertical_shift_max=12,
        color_shift_x=5,
        color_shift_y=5,
        scanline_intensity=0.45,
        noise_intensity=0.4,
        ghost_blend=0.5
    ),
    "quantum_matrix_tear": GlitchPreset(
        id="quantum_matrix_tear",
        name="Quantum Matrix Tear",
        description="High-frequency macroblock corruption, payload bitflips, and pseudo-random byte replacement.",
        slice_height=8,
        horizontal_shift_max=50,
        vertical_block_width=12,
        vertical_shift_max=35,
        color_shift_x=15,
        color_shift_y=15,
        block_artifact_size=16,
        block_artifact_probability=0.6,
        bitflip_rate=0.005,
        scanline_intensity=0.5
    ),
    "audio_reactive_beat": GlitchPreset(
        id="audio_reactive_beat",
        name="Audio-Reactive Beat Glitch",
        description="Dynamic audiovisual datamosh responding to transient bass peaks and rhythmic kick transients.",
        slice_height=10,
        horizontal_shift_max=36,
        vertical_block_width=20,
        vertical_shift_max=24,
        color_shift_x=18,
        color_shift_y=10,
        scanline_intensity=0.4,
        noise_intensity=0.25,
        ghost_blend=0.55,
    ),
}


def get_preset(preset_id: str) -> GlitchPreset:
    """Retrieve preset by ID or return default."""
    return PRESETS.get(preset_id, PRESETS["h264_iframe_drop"])


def list_presets() -> List[Dict[str, Any]]:
    """Return list of all preset metadata."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "slice_height": p.slice_height,
            "horizontal_shift_max": p.horizontal_shift_max,
            "color_shift_x": p.color_shift_x,
            "color_shift_y": p.color_shift_y,
            "scanline_intensity": p.scanline_intensity,
            "noise_intensity": p.noise_intensity,
            "ghost_blend": p.ghost_blend,
        }
        for p in PRESETS.values()
    ]


def modulate_preset_with_audio(
    base_preset: GlitchPreset,
    audio_energy: float = 0.5,
    is_beat: bool = False,
) -> GlitchPreset:
    """Dynamically modulate a GlitchPreset's parameters based on audio amplitude or energy.

    Args:
        base_preset: The base template preset.
        audio_energy: Normalized audio energy/amplitude in [0.0, 1.0].
        is_beat: True if the current frame corresponds to a transient/rhythmic beat.

    Returns:
        GlitchPreset: Modulated preset with dynamic glitch intensity.
    """
    energy = max(0.0, min(1.0, float(audio_energy)))
    beat_mult = 1.8 if is_beat else 1.0

    return GlitchPreset(
        id=f"{base_preset.id}_audio_mod",
        name=f"{base_preset.name} (Audio Reactive)",
        description=f"Audio modulated at energy={energy:.2f} (beat={is_beat})",
        slice_height=max(2, int(base_preset.slice_height * (1.2 if is_beat else 1.0))),
        horizontal_shift_max=int(base_preset.horizontal_shift_max * (1.0 + 2.0 * energy) * beat_mult),
        vertical_block_width=base_preset.vertical_block_width,
        vertical_shift_max=int(base_preset.vertical_shift_max * (1.0 + 1.5 * energy) * beat_mult),
        color_shift_x=int(base_preset.color_shift_x * (1.0 + 2.5 * energy) * beat_mult),
        color_shift_y=int(base_preset.color_shift_y * (1.0 + 2.0 * energy) * beat_mult),
        scanline_intensity=min(1.0, base_preset.scanline_intensity * (1.0 + 0.5 * energy)),
        scanline_frequency=base_preset.scanline_frequency,
        block_artifact_size=base_preset.block_artifact_size,
        block_artifact_probability=min(1.0, base_preset.block_artifact_probability * (1.0 + 1.2 * energy)),
        bitflip_rate=base_preset.bitflip_rate * (2.0 if is_beat else 1.0),
        ghost_blend=min(1.0, base_preset.ghost_blend * (1.0 + 0.3 * energy)),
        noise_intensity=min(1.0, base_preset.noise_intensity * (1.0 + 1.5 * energy)),
    )

