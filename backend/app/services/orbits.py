"""Orbit maths: SGP4 propagation to sub-satellite points.

SGP4 returns positions in the TEME frame (Earth-centred, not rotating with
the Earth). To get a longitude on the ground we rotate by Greenwich Mean
Sidereal Time (GMST) at the same instant.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
from sgp4.api import Satrec, SatrecArray, jday

EARTH_RADIUS_KM = 6371.0
MU_KM3_S2 = 398600.4418


def gmst_deg_from_jd(jd_ut1: float) -> float:
    """Greenwich Mean Sidereal Time in degrees (IAU 1982, low-precision form).

    Accurate to well under a second of time for dates near J2000, which is
    far better than a ground-track plot needs.
    """
    d = jd_ut1 - 2451545.0
    t = d / 36525.0
    gmst = 280.46061837 + 360.98564736629 * d + 0.000387933 * t * t - (t ** 3) / 38710000.0
    return gmst % 360.0


def gmst_deg(when: datetime) -> float:
    when = when.astimezone(timezone.utc)
    jd, fr = jday(when.year, when.month, when.day, when.hour, when.minute,
                  when.second + when.microsecond / 1e6)
    return gmst_deg_from_jd(jd + fr)


def teme_to_latlonalt(r: tuple[float, float, float] | np.ndarray, gmst: float) -> tuple[float, float, float]:
    x, y, z = float(r[0]), float(r[1]), float(r[2])
    rad = math.sqrt(x * x + y * y + z * z)
    lat = math.degrees(math.asin(z / rad))
    ra = math.degrees(math.atan2(y, x))
    lon = (ra - gmst + 540.0) % 360.0 - 180.0
    return lat, lon, rad - EARTH_RADIUS_KM


def propagate(l1: str, l2: str, when: datetime) -> tuple[float, float, float, float]:
    """(lat, lon, altitude_km, speed_km_s) for one TLE at one instant."""
    sat = Satrec.twoline2rv(l1, l2)
    when = when.astimezone(timezone.utc)
    jd, fr = jday(when.year, when.month, when.day, when.hour, when.minute,
                  when.second + when.microsecond / 1e6)
    err, r, v = sat.sgp4(jd, fr)
    if err != 0:
        raise ValueError(f"SGP4 error {err}")
    lat, lon, alt = teme_to_latlonalt(r, gmst_deg_from_jd(jd + fr))
    return lat, lon, alt, math.sqrt(sum(c * c for c in v))


def ground_track(l1: str, l2: str, center: datetime, minutes_before: int = 90,
                 minutes_after: int = 90, step_min: int = 2) -> list[dict]:
    out = []
    for m in range(-minutes_before, minutes_after + 1, step_min):
        t = center + timedelta(minutes=m)
        try:
            lat, lon, alt, _ = propagate(l1, l2, t)
        except ValueError:
            continue
        out.append({"time": t.isoformat(), "lat": round(lat, 3), "lon": round(lon, 3),
                    "alt_km": round(alt, 1), "offset_min": m})
    return out


# ------------------------------------------------------------------ batch --
@dataclass
class _Batch:
    key: tuple
    ids: list
    array: SatrecArray


_batch_cache: _Batch | None = None


def positions_now(rows: list[tuple], when: datetime | None = None) -> dict:
    """Propagate many satellites at once.

    rows: [(key, tle_line1, tle_line2), ...] -> {key: (lat, lon, alt_km, speed)}
    The SatrecArray is cached until the catalogue changes.
    """
    global _batch_cache
    when = (when or datetime.now(timezone.utc)).astimezone(timezone.utc)
    valid = [(k, a, b) for k, a, b in rows if a and b]
    if not valid:
        return {}
    cache_key = tuple((k, a[18:32]) for k, a, _ in valid)
    if _batch_cache is None or _batch_cache.key != cache_key:
        sats, ids = [], []
        for k, a, b in valid:
            try:
                sats.append(Satrec.twoline2rv(a, b))
                ids.append(k)
            except Exception:
                continue
        _batch_cache = _Batch(cache_key, ids, SatrecArray(sats))
    jd, fr = jday(when.year, when.month, when.day, when.hour, when.minute,
                  when.second + when.microsecond / 1e6)
    e, r, v = _batch_cache.array.sgp4(np.array([jd]), np.array([fr]))
    gmst = gmst_deg_from_jd(jd + fr)
    out = {}
    for i, k in enumerate(_batch_cache.ids):
        if e[i][0] != 0:
            continue
        lat, lon, alt = teme_to_latlonalt(r[i][0], gmst)
        out[k] = (lat, lon, alt, float(np.linalg.norm(v[i][0])))
    return out


# --------------------------------------------------------- orbital params --
def orbit_params(l1: str, l2: str) -> dict:
    """Human-readable orbital elements decoded from a TLE."""

    def num(line: str, start: int, end: int) -> float:
        try:
            return float(line[start:end].strip() or 0)
        except ValueError:
            return 0.0

    inclination = num(l2, 8, 16)
    raan = num(l2, 17, 25)
    try:
        eccentricity = float(f"0.{l2[26:33].strip() or '0'}")
    except ValueError:
        eccentricity = 0.0
    arg_perigee = num(l2, 34, 42)
    mean_anomaly = num(l2, 43, 51)
    mean_motion = num(l2, 52, 63)
    period_min = 1440.0 / mean_motion if mean_motion > 0 else 0.0
    n_rad_s = mean_motion * 2 * math.pi / 86400.0
    semi_major = (MU_KM3_S2 / n_rad_s ** 2) ** (1 / 3) if mean_motion > 0 else 0.0
    epoch = None
    try:
        yy = int(l1[18:20])
        ddd = float(l1[20:32])
        year = 2000 + yy if yy < 57 else 1900 + yy
        epoch = datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=ddd - 1)
    except ValueError:
        pass
    return {
        "inclination_deg": round(inclination, 2),
        "raan_deg": round(raan, 2),
        "eccentricity": round(eccentricity, 7),
        "arg_perigee_deg": round(arg_perigee, 2),
        "mean_anomaly_deg": round(mean_anomaly, 2),
        "mean_motion_revs_per_day": round(mean_motion, 4),
        "period_minutes": round(period_min, 1),
        "semi_major_axis_km": round(semi_major, 1),
        "perigee_alt_km": round(semi_major * (1 - eccentricity) - EARTH_RADIUS_KM, 0),
        "apogee_alt_km": round(semi_major * (1 + eccentricity) - EARTH_RADIUS_KM, 0),
        "epoch": epoch.isoformat() if epoch else None,
        "tle_line1": l1,
        "tle_line2": l2,
    }


# ------------------------------------------------------------ demo TLEs --
def _checksum(line: str) -> int:
    total = 0
    for ch in line[:68]:
        if ch.isdigit():
            total += int(ch)
        elif ch == "-":
            total += 1
    return total % 10


def make_tle(norad: int, inclination: float, raan: float, eccentricity: float,
             arg_perigee: float, mean_anomaly: float, mean_motion: float,
             epoch: datetime | None = None) -> tuple[str, str]:
    """Build a syntactically valid TLE pair (used for the offline demo world)."""
    epoch = (epoch or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = datetime(epoch.year, 1, 1, tzinfo=timezone.utc)
    doy = (epoch - start).total_seconds() / 86400.0 + 1.0
    epoch_str = f"{epoch.year % 100:02d}{doy:012.8f}"
    l1 = (f"1 {norad:05d}U 26001A   {epoch_str}  .00000000  00000-0  00000-0 0  999")
    l1 = l1[:68].ljust(68)
    l1 += str(_checksum(l1))
    ecc = f"{eccentricity:.7f}"[2:]
    l2 = (f"2 {norad:05d} {inclination:8.4f} {raan % 360:8.4f} {ecc} "
          f"{arg_perigee % 360:8.4f} {mean_anomaly % 360:8.4f} {mean_motion:11.8f}    1")
    l2 = l2[:68].ljust(68)
    l2 += str(_checksum(l2))
    return l1, l2


def now_monotonic() -> float:
    return time.monotonic()
