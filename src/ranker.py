"""
Part B — reads the loads spreadsheet, applies the driver's profile constraints,
computes effective rate per mile using haversine distances, and returns the
top 3 eligible loads ranked highest to lowest.

Effective rate/mile = price / (deadhead_to_origin + loaded_miles + deadhead_home)

All distances use straight-line haversine from provided lat/lon coordinates.
"""

import logging
import pandas as pd
from src.geo import haversine

logger = logging.getLogger(__name__)


def load_loads(xlsx_path: str) -> pd.DataFrame:
    """Read the Loads sheet from the workbook."""
    logger.info(f"Loading loads sheet 'Loads' from workbook: {xlsx_path}")
    df = pd.read_excel(xlsx_path, sheet_name="Loads")
    df.columns = df.columns.str.strip()
    logger.info(f"Successfully loaded {len(df)} loads from workbook.")
    return df


def _to_float(val):
    """Convert a cell value to float; return None if missing or non-numeric."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def rank_loads(loads_df: pd.DataFrame, profile: dict) -> dict:
    """
    Filter and rank loads against the driver profile.

    Returns a dict with:
      - top3: list of up to 3 dicts (load details + effective_rate_per_mile)
      - rejected: list of dicts explaining each ineligible or skipped load
    """
    truck_lat = profile["current_lat"]
    truck_lon = profile["current_lon"]
    home_lat = profile["home_lat"]
    home_lon = profile["home_lon"]
    min_rate = profile["min_rate_per_mile"]
    equipment_ok = [e.strip().lower() for e in profile["equipment_types"]]
    max_weight = profile["weight_capacity_lb"]

    logger.info("Filtering and ranking loads against driver profile:")
    logger.info(f"  Current location: {profile['current_location']} ({truck_lat}, {truck_lon})")
    logger.info(f"  Home base: {profile['home_base']} ({home_lat}, {home_lon})")
    logger.info(f"  Min rate: ${min_rate:.2f}/mi, Equipment: {profile['equipment_types']}, Max weight: {max_weight:,} lb")

    eligible = []
    rejected = []

    for _, row in loads_df.iterrows():
        load_id = str(row.get("Load ID", "?")).strip()
        trailer = str(row.get("Trailer", "")).strip()
        weight = _to_float(row.get("Weight"))
        price = _to_float(row.get("Price ($)"))
        origin = str(row.get("Origin", "")).strip()
        dest_raw = row.get("Destination", "")
        dest = str(dest_raw).strip() if pd.notna(dest_raw) else None

        o_lat = _to_float(row.get("Origin Lat"))
        o_lon = _to_float(row.get("Origin Lon"))
        d_lat = _to_float(row.get("Dest Lat"))
        d_lon = _to_float(row.get("Dest Lon"))

        # ── Missing data handling ──────────────────────────────────────────
        # Decision: skip loads missing price OR destination coords.
        # Without price we cannot compute a rate.
        # Without destination coords we cannot compute deadhead-home distance.
        # Both are essential — we skip and log rather than crash or guess.
        if price is None:
            reason = "skipped - missing price; cannot compute effective rate"
            logger.warning(f"Load {load_id}: {reason}")
            rejected.append({
                "load_id": load_id,
                "reason": reason,
            })
            continue

        if d_lat is None or d_lon is None or dest in (None, "", "MISSING"):
            reason = "skipped - missing destination coordinates; cannot compute deadhead-home"
            logger.warning(f"Load {load_id}: {reason}")
            rejected.append({
                "load_id": load_id,
                "reason": reason,
            })
            continue

        # ── Equipment filter ───────────────────────────────────────────────
        if trailer.lower() not in equipment_ok:
            reason = f"ineligible - trailer type '{trailer}' not in driver's equipment {profile['equipment_types']}"
            logger.info(f"Load {load_id}: {reason}")
            rejected.append({
                "load_id": load_id,
                "reason": reason,
                "price": price,
            })
            continue

        # ── Weight filter ──────────────────────────────────────────────────
        if weight is not None and weight > max_weight:
            reason = f"ineligible - load weight {weight:,.0f} lb exceeds capacity {max_weight:,} lb"
            logger.info(f"Load {load_id}: {reason}")
            rejected.append({
                "load_id": load_id,
                "reason": reason,
                "price": price,
            })
            continue

        # ── Distance & effective rate ──────────────────────────────────────
        dh_to_origin = haversine(truck_lat, truck_lon, o_lat, o_lon)
        loaded_miles = haversine(o_lat, o_lon, d_lat, d_lon)
        dh_home = haversine(d_lat, d_lon, home_lat, home_lon)
        total_miles = dh_to_origin + loaded_miles + dh_home

        if total_miles == 0:
            reason = "skipped - total distance is zero (same coordinates)"
            logger.warning(f"Load {load_id}: {reason}")
            rejected.append({
                "load_id": load_id,
                "reason": reason,
            })
            continue

        eff_rate = price / total_miles

        # ── Rate filter ────────────────────────────────────────────────────
        if eff_rate < min_rate:
            reason = f"ineligible - effective rate ${eff_rate:.3f}/mi is below driver's minimum ${min_rate:.2f}/mi"
            logger.info(f"Load {load_id}: {reason} (miles: {total_miles:.1f}, price: ${price:.2f})")
            rejected.append({
                "load_id": load_id,
                "reason": reason,
                "price": price,
                "effective_rate_per_mile": round(eff_rate, 3),
            })
            continue

        logger.info(
            f"Load {load_id}: eligible! rate=${eff_rate:.3f}/mi (deadhead_to_orig={dh_to_origin:.1f} mi, "
            f"loaded={loaded_miles:.1f} mi, deadhead_home={dh_home:.1f} mi, total={total_miles:.1f} mi)"
        )
        eligible.append({
            "load_id": load_id,
            "origin": origin,
            "destination": dest,
            "trailer": trailer,
            "weight_lb": weight,
            "price_usd": price,
            "deadhead_to_origin_mi": round(dh_to_origin, 1),
            "loaded_miles": round(loaded_miles, 1),
            "deadhead_home_mi": round(dh_home, 1),
            "total_miles": round(total_miles, 1),
            "effective_rate_per_mile": round(eff_rate, 3),
        })

    # Sort eligible loads by effective rate, descending
    eligible.sort(key=lambda x: x["effective_rate_per_mile"], reverse=True)
    
    logger.info(f"Filtering complete. Total processed: {len(loads_df)}, Eligible: {len(eligible)}, Rejected: {len(rejected)}")

    return {
        "top3": eligible[:3],
        "all_eligible": eligible,
        "rejected": rejected,
    }


if __name__ == "__main__":
    import json, pathlib, sys
    # Setup basic logging for standalone execution
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    here = pathlib.Path(__file__).parent.parent
    df = load_loads(str(here / "data" / "Good_fit_test_clean.xlsx"))

    # Sample profile for standalone testing
    sample_profile = {
        "current_location": "Dallas, TX",
        "current_lat": 32.7767,
        "current_lon": -96.7970,
        "home_base": "San Antonio, TX",
        "home_lat": 29.4241,
        "home_lon": -98.4936,
        "min_rate_per_mile": 2.0,
        "equipment_types": ["Hotshot", "Gooseneck"],
        "weight_capacity_lb": 44000,
    }

    results = rank_loads(df, sample_profile)
    print(json.dumps(results, indent=2))

