"""Torrent quality scoring engine backed by RTN (rank-torrent-name).

Two-layer ranking:
  1. Resolution tier  — primary sort key (higher tier always wins)
  2. Format score     — secondary sort within same tier

Usage::

    from patchy_bot.quality import score_torrent, quality_label

    ts = score_torrent("Movie.2024.1080p.WEB-DL.DDP5.1.H264-NTG", size=4_000_000_000, seeds=120)
    if not ts.is_rejected:
        label = quality_label(ts.parsed)  # "1080p WEB-DL x264 DDP [NTG]"
"""

from __future__ import annotations

import dataclasses
import re

from RTN import parse
from RTN.models import ParsedData

# ---------------------------------------------------------------------------
# Resolution tiers
# ---------------------------------------------------------------------------

_RESOLUTION_TIERS: dict[str, int] = {"2160p": 4, "1080p": 3, "720p": 2, "480p": 1}

# ---------------------------------------------------------------------------
# Release-group allow/deny lists
# ---------------------------------------------------------------------------

# Low-quality groups — not hard-rejected, but penalised -500 so they sink to bottom
LQ_GROUPS: set[str] = {
    "yify",
    "yts",
    "evo",
    "axxo",
    "korsub",
    "bon",
    "fgt",
    "tgx",
    "ipt",
    "stuttershit",
    "tbs",
    "cakes",
}

# High-quality encode / WEB-DL groups — +30 bonus
HQ_GROUPS: set[str] = {
    # Remux / encode
    "framest0r",
    "ctrlhd",
    "don",
    "epsilon",
    "hifi",
    "ntb",
    "hallowed",
    "ftw-hd",
    "wiki",
    "decibelz",
    "za1no",
    # WEB-DL
    "ntg",
    "flux",
    "peculate",
    "cmrg",
    "kings",
    "mzabi",
    "cryptographers",
    "ajax",
    "wayne",
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class TorrentScore:
    """Immutable scoring result for one torrent.

    Attributes:
        resolution_tier: Primary sort key — 4=2160p, 3=1080p, 2=720p, 1=480p, 0=unknown.
        format_score: Secondary sort key within the same tier.
        is_rejected: True when the torrent should never be offered to the user.
        reject_reason: Short human-readable string if is_rejected, else None.
        parsed: RTN ParsedData object with all extracted metadata.
    """

    resolution_tier: int
    format_score: int
    is_rejected: bool
    reject_reason: str | None
    parsed: ParsedData


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def parse_quality(name: str) -> ParsedData:
    """Thin wrapper around RTN parse().

    Args:
        name: Raw torrent name string.

    Returns:
        RTN ParsedData with resolution, codec, quality, audio, hdr, group, etc.
    """
    return parse(name)


def is_season_pack(name: str, parsed: ParsedData | None = None) -> bool:
    """Return True if the torrent is a season pack rather than a single episode.

    Uses RTN's parsed ``seasons``, ``episodes``, and ``complete`` fields when
    a pre-parsed object is provided, otherwise falls back to regex on the raw name.

    Args:
        name: Raw torrent name string.
        parsed: Optional pre-parsed RTN ParsedData (avoids double parse).

    Returns:
        True for season packs, series complete, or multi-episode bundles.
    """
    if parsed is not None:
        if getattr(parsed, "complete", False):
            return True
        seasons = getattr(parsed, "seasons", []) or []
        episodes = getattr(parsed, "episodes", []) or []
        if seasons and not episodes:
            return True
        return False

    low = name.lower()
    if re.search(r"\bcomplete\b", low):
        return True
    # S01 without a following E number — season pack
    if re.search(r"\bs\d{1,2}(?!e\d)", low) and not re.search(r"\bs\d{1,2}e\d{1,2}\b", low):
        return True
    if re.search(r"\bseason[\.\s_-]?\d{1,2}\b", low) and not re.search(r"\bs\d{1,2}e\d{1,2}\b", low):
        return True
    return False


def score_torrent(
    name: str,
    size: int,
    seeds: int,
    media_type: str = "movie",
) -> TorrentScore:
    """Score a torrent for quality ranking.

    Higher ``resolution_tier`` always beats a lower tier.  Within the same
    tier, higher ``format_score`` wins.  Rejected torrents have
    ``is_rejected=True`` and ``format_score=-9999``.

    Args:
        name: Raw torrent name string.
        size: File size in bytes (0 = unknown, skips size check).
        seeds: Current seeder count.
        media_type: ``"movie"`` or ``"episode"`` — affects size sanity ranges.

    Returns:
        TorrentScore with resolution_tier, format_score, is_rejected, and parsed data.
    """
    parsed = parse_quality(name)
    tier = _RESOLUTION_TIERS.get(parsed.resolution, 0)
    is_4k = tier == 4

    # ------------------------------------------------------------------
    # Hard rejections
    # ------------------------------------------------------------------
    if parsed.trash:
        return TorrentScore(tier, -9999, True, "garbage source (CAM/TS/SCR)", parsed)
    if parsed.upscaled:
        return TorrentScore(tier, -9999, True, "upscaled content", parsed)
    if (parsed.codec or "").lower() == "av1":
        return TorrentScore(tier, -9999, True, "AV1 codec — poor compatibility", parsed)
    if seeds == 0:
        return TorrentScore(tier, -9999, True, "zero seeders", parsed)

    score = 0

    # ------------------------------------------------------------------
    # Source / release type points
    # ------------------------------------------------------------------
    quality_str = (parsed.quality or "").lower()
    if "remux" in quality_str:
        score += 100
    elif "bluray" in quality_str or "blu-ray" in quality_str or "bdrip" in quality_str:
        score += 80
    elif quality_str == "web-dl":
        score += 70
    elif quality_str == "webrip":
        score += 55
    elif "hdtv" in quality_str:
        score += 35
    elif "dvdrip" in quality_str:
        score += 15

    # ------------------------------------------------------------------
    # Codec points — resolution-aware
    # ------------------------------------------------------------------
    codec = (parsed.codec or "").lower()
    if is_4k:
        if codec == "hevc":
            score += 80
        elif codec == "avc":
            score += 40
        # av1 already hard-rejected above; other codecs get 0
    else:
        if codec == "avc":
            score += 70
        elif codec == "hevc":
            score -= 50  # x265 at 1080p causes transcoding on many clients
    # xvid always penalised regardless of resolution (RTN maps divx → xvid too)
    if codec == "xvid":
        score -= 200

    # ------------------------------------------------------------------
    # Audio points — compatibility-aware
    # RTN normalises: DD5.1 / AC3 → "Dolby Digital"
    #                 DDP → "Dolby Digital Plus"
    #                 DTS-HD MA / DTS:X → "DTS Lossless"
    #                 TrueHD → "TrueHD"
    #                 Atmos tag → "Atmos"
    # ------------------------------------------------------------------
    audio_list = [a.lower() for a in (parsed.audio or [])]
    audio_str = " ".join(audio_list)

    if is_4k:
        # High-fidelity preferred at 4K
        if "truehd" in audio_str and "atmos" in audio_str:
            score += 100
        elif "truehd" in audio_str:
            score += 90
        elif "dts lossless" in audio_str:
            score += 85
        elif "atmos" in audio_str:
            score += 70
        elif "dolby digital plus" in audio_str:
            score += 50
        elif "dolby digital" in audio_str:
            score += 40
    else:
        # Universal playback compatibility preferred at 1080p and below
        if "dolby digital plus" in audio_str and "atmos" in audio_str:
            score += 70
        elif "dolby digital plus" in audio_str:
            score += 60
        elif "dolby digital" in audio_str:
            score += 50
        elif "aac" in audio_str:
            score += 35
        elif "dts lossless" in audio_str:
            score += 15  # neutral — lossless but heavy for 1080p clients
        elif "dts lossy" in audio_str or any("dts" in a for a in audio_list):
            score += 30
        elif "truehd" in audio_str:
            score += 15  # neutral at 1080p
        elif "mp3" in audio_str:
            score += 10

    # ------------------------------------------------------------------
    # Seed bucket points
    # ------------------------------------------------------------------
    if seeds >= 50:
        score += 60
    elif seeds >= 25:
        score += 50
    elif seeds >= 10:
        score += 40
    elif seeds >= 5:
        score += 25
    elif seeds >= 3:
        score += 10
    elif seeds >= 1:
        score += 2
    # seeds == 0 already hard-rejected above

    # ------------------------------------------------------------------
    # Bonuses
    # ------------------------------------------------------------------
    if parsed.proper or parsed.repack:
        score += 15

    hdr_list = [h.lower() for h in (parsed.hdr or [])]
    if is_4k:
        if any("dv" in h or "dolby vision" in h for h in hdr_list):
            score += 25
        if any(h in ("hdr", "hdr10", "hdr10+") for h in hdr_list):
            score += 20
    else:
        # DV at 1080p typically forces transcoding
        if any("dv" in h or "dolby vision" in h for h in hdr_list):
            score -= 10

    group_lower = (parsed.group or "").lower()
    if group_lower in HQ_GROUPS:
        score += 30
    elif group_lower in LQ_GROUPS:
        score -= 500

    if parsed.network:
        score += 5  # known streaming platform implies official WEB source

    # ------------------------------------------------------------------
    # File size sanity check
    # ------------------------------------------------------------------
    if size > 0:
        _GB = 1024**3
        _MB = 1024**2
        size_ranges: dict[str, dict[int, tuple[int, int]]] = {
            "movie": {
                4: (5 * _GB, 80 * _GB),
                3: (int(1.5 * _GB), 20 * _GB),
                2: (700 * _MB, 8 * _GB),
                1: (300 * _MB, 4 * _GB),
            },
            "episode": {
                4: (1 * _GB, 15 * _GB),
                3: (300 * _MB, 4 * _GB),
                2: (200 * _MB, 2 * _GB),
                1: (100 * _MB, 1 * _GB),
            },
        }
        mt = media_type if media_type in size_ranges else "movie"
        size_range = size_ranges[mt].get(tier)
        if size_range:
            min_s, max_s = size_range
            if is_season_pack(name, parsed):
                max_s *= 24  # season packs can be much larger
                min_s = 0  # skip minimum for packs
            if size < min_s:
                score -= 100
            elif size > max_s:
                score -= 20

    return TorrentScore(tier, score, False, None, parsed)


# ---------------------------------------------------------------------------
# UI display helper
# ---------------------------------------------------------------------------

_CODEC_ABBREV: dict[str, str] = {
    "avc": "x264",
    "hevc": "x265",
    "av1": "AV1",
    "xvid": "XviD",
}

_AUDIO_ABBREV: dict[str, str] = {
    "dolby digital plus": "DDP",
    "dolby digital": "DD5.1",
    "truehd": "TrueHD",
    "dts lossy": "DTS",
    "dts lossless": "DTS-HD MA",
    "aac": "AAC",
    "atmos": "Atmos",
    "mp3": "MP3",
}


def quality_label(parsed: ParsedData) -> str:
    """Build a short quality label for UI display.

    Args:
        parsed: RTN ParsedData from parse_quality() or score_torrent().parsed.

    Returns:
        Human-readable label, e.g. ``"1080p WEB-DL x264 DDP Atmos [NTG]"``.
        Returns ``"Unknown"`` if no fields could be extracted.

    Example::

        r = parse_quality("Show.S01E03.1080p.WEB-DL.DDP5.1.Atmos.H264-NTG")
        print(quality_label(r))  # "1080p WEB-DL x264 DDP Atmos [NTG]"
    """
    parts: list[str] = []

    if parsed.resolution and parsed.resolution != "unknown":
        parts.append(parsed.resolution)

    if parsed.quality:
        parts.append(parsed.quality)

    if parsed.codec:
        parts.append(_CODEC_ABBREV.get(parsed.codec.lower(), parsed.codec.upper()))

    if parsed.audio:
        seen: set[str] = set()
        for raw_audio in parsed.audio:
            abbr = _AUDIO_ABBREV.get(raw_audio.lower(), raw_audio)
            if abbr not in seen:
                seen.add(abbr)
                parts.append(abbr)

    for hdr_flag in parsed.hdr or []:
        parts.append(hdr_flag)

    if parsed.group:
        parts.append(f"[{parsed.group}]")

    return " ".join(parts) if parts else "Unknown"
