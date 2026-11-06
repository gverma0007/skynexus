"""Seed real airports + routes for every monitored region.

Live ADS-B ingestion attaches aircraft positions to flight routes, so each
region needs at least one route (origin + destination airport) in the DB.
The demo dataset seeds airports only for its 5 scenario regions — this
module covers all 15 monitored regions with real IATA hubs, so the live
connector produces data everywhere.

Also provides `purge_synthetic()`, which removes all demo_dataset rows so
the stack can run on live data only.
"""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.aviation import (
    Airport,
    Event,
    FlightObservation,
    FlightRoute,
    Region,
    SatelliteObservation,
    WeatherObservation,
)

logger = logging.getLogger("seed_airports")

# Real airport hubs per monitored region: (iata, name, lat, lon).
# First entry is the region anchor (route origin); the rest become
# destinations so /api/flights/live arcs render across the region.
AIRPORTS: dict[str, list[tuple[str, str, float, float]]] = {
    "Middle East": [
        ("DXB", "Dubai Intl", 25.2532, 55.3657),
        ("DOH", "Hamad Intl", 25.2731, 51.6081),
        ("RUH", "King Khalid Intl", 24.9576, 46.6988),
        ("TLV", "Ben Gurion Intl", 32.0114, 34.9866),
        ("BGW", "Baghdad Intl", 33.2626, 44.2344),
    ],
    "Eastern Europe": [
        ("WAW", "Warsaw Chopin", 52.1657, 20.9671),
        ("OTP", "Bucharest Henri Coanda", 44.5711, 26.0850),
        ("BUD", "Budapest Ferenc Liszt", 47.4369, 19.2556),
        ("KBP", "Kyiv Boryspil", 50.3450, 30.8947),
        ("VNO", "Vilnius Intl", 54.6341, 25.2858),
    ],
    "South China Sea": [
        ("SIN", "Singapore Changi", 1.3644, 103.9915),
        ("HKG", "Hong Kong Intl", 22.3080, 113.9185),
        ("MNL", "Manila Ninoy Aquino", 14.5086, 121.0198),
        ("SGN", "Ho Chi Minh Tan Son Nhat", 10.8188, 106.6519),
        ("KUL", "Kuala Lumpur Intl", 2.7456, 101.7099),
    ],
    "North Atlantic": [
        ("LHR", "London Heathrow", 51.4700, -0.4543),
        ("JFK", "New York JFK", 40.6413, -73.7781),
        ("KEF", "Keflavik Intl", 63.9850, -22.6056),
        ("DUB", "Dublin Intl", 53.4213, -6.2701),
        ("LIS", "Lisbon Humberto Delgado", 38.7742, -9.1342),
    ],
    "Pacific": [
        ("HNL", "Honolulu Daniel K. Inouye", 21.3187, -157.9224),
        ("NRT", "Tokyo Narita", 35.7719, 140.3929),
        ("SYD", "Sydney Kingsford Smith", -33.9399, 151.1753),
        ("GUM", "Antonio B. Won Pat Intl", 13.4834, 144.7980),
        ("AKL", "Auckland Intl", -37.0082, 174.7850),
    ],
    "Black Sea": [
        ("ODS", "Odesa Intl", 46.4268, 30.6757),
        ("VAR", "Varna Intl", 43.2321, 27.8617),
        ("BUS", "Batumi Intl", 41.6103, 41.5992),
        ("IST", "Istanbul Airport", 41.2753, 28.7519),
    ],
    "Red Sea": [
        ("JED", "Jeddah King Abdulaziz", 21.6796, 39.1565),
        ("HRG", "Hurghada Intl", 27.1783, 33.7994),
        ("ASM", "Asmara Intl", 15.2914, 38.9096),
        ("MRK", "Marsa Alam Intl", 25.5531, 34.5850),
    ],
    "Taiwan Strait": [
        ("TPE", "Taiwan Taoyuan Intl", 25.0777, 121.2328),
        ("KHH", "Kaohsiung Intl", 22.5771, 120.3498),
        ("XMN", "Xiamen Gaoqi Intl", 24.5440, 118.1277),
        ("FOC", "Fuzhou Changle Intl", 25.9350, 119.6652),
    ],
    "Korean Peninsula": [
        ("ICN", "Seoul Incheon Intl", 37.4602, 126.4407),
        ("GMP", "Seoul Gimpo Intl", 37.5583, 126.7906),
        ("CJU", "Jeju Intl", 33.5064, 126.4915),
        ("PUS", "Busan Gimhae", 35.1795, 128.9382),
    ],
    "Eastern Mediterranean": [
        ("ATH", "Athens Intl", 37.9364, 23.9445),
        ("LCA", "Larnaca Intl", 34.8751, 33.6249),
        ("BEY", "Beirut Rafic Hariri", 33.8209, 35.4884),
        ("PFO", "Paphos Intl", 34.7179, 32.4857),
    ],
    "Baltic Sea": [
        ("RIX", "Riga Intl", 56.9236, 23.9711),
        ("TLL", "Tallinn Lennart Meri", 59.4133, 24.8328),
        ("GDN", "Gdansk Lech Walesa", 54.3776, 18.4662),
        ("HEL", "Helsinki Vantaa", 60.3172, 24.9633),
    ],
    "Horn of Africa": [
        ("ADD", "Addis Ababa Bole Intl", 8.9779, 38.7993),
        ("NBO", "Nairobi Jomo Kenyatta", -1.3192, 36.9278),
        ("DJJ", "Djibouti Ambouli", 11.5472, 43.1596),
        ("MGQ", "Mogadishu Aden Adde", 2.9146, 45.4247),
    ],
    "Bay of Bengal": [
        ("CCU", "Kolkata Netaji Subhas", 22.6547, 88.4467),
        ("DAC", "Dhaka Hazrat Shahjalal", 23.8433, 90.3978),
        ("CMB", "Colombo Bandaranaike", 7.1808, 79.8841),
        ("MAA", "Chennai Intl", 12.9941, 80.1709),
    ],
    "Caribbean": [
        ("PTY", "Panama Tocumen Intl", 9.0714, -79.3835),
        ("SJU", "San Juan Luis Munoz Marin", 18.4394, -66.0018),
        ("HAV", "Havana Jose Marti", 22.9892, -82.4091),
        ("SDQ", "Santo Domingo Las Americas", 18.4297, -69.6689),
    ],
    "Gulf of Guinea": [
        ("LOS", "Lagos Murtala Muhammed", 6.5774, 3.3212),
        ("ACC", "Accra Kotoka Intl", 5.6052, -0.1668),
        ("ABJ", "Abidjan Felix Houphouet Boigny", 5.2614, -3.9263),
        ("DLA", "Douala Intl", 4.0063, 9.7189),
    ],
    "India-Pakistan Border": [
        ("DEL", "Indira Gandhi Intl", 28.5562, 77.1000),
        ("LHE", "Lahore Allama Iqbal Intl", 31.5216, 74.4036),
        ("ISB", "Islamabad Intl", 33.5492, 72.8258),
        ("ATQ", "Amritsar Sri Guru Ram Dass", 31.7096, 74.7973),
    ],
}


def upsert_airports() -> dict:
    """Insert/attach airports and ensure each region has at least one route."""
    db: Session = SessionLocal()
    inserted = 0
    routes_created = 0
    try:
        region_map = {r.name: r for r in db.query(Region).all()}
        for region_name, hubs in AIRPORTS.items():
            region = region_map.get(region_name)
            if region is None:
                logger.warning("Region %s not found — run seed_regions first", region_name)
                continue

            airports: list[Airport] = []
            for iata, name, lat, lon in hubs:
                airport = db.query(Airport).filter(Airport.iata_code == iata).first()
                if airport is None:
                    airport = Airport(
                        iata_code=iata,
                        name=name,
                        geom=f"POINT({lon} {lat})",
                        region_id=region.id,
                    )
                    db.add(airport)
                    inserted += 1
                else:
                    # Keep coordinates/attachment fresh on re-seed.
                    airport.geom = f"POINT({lon} {lat})"
                    airport.region_id = region.id
                airports.append(airport)
            db.flush()

            anchor = airports[0]
            for dest in airports[1:]:
                existing = (
                    db.query(FlightRoute)
                    .filter(
                        FlightRoute.origin_airport_id == anchor.id,
                        FlightRoute.dest_airport_id == dest.id,
                    )
                    .first()
                )
                if existing is None:
                    db.add(
                        FlightRoute(
                            origin_airport_id=anchor.id,
                            dest_airport_id=dest.id,
                            region_id=region.id,
                        )
                    )
                    routes_created += 1
        db.commit()
        print(
            f"Airports processed: {inserted} inserted, "
            f"{routes_created} routes created."
        )
        return {"airports_inserted": inserted, "routes_created": routes_created}
    finally:
        db.close()


def purge_synthetic() -> dict:
    """Remove all demo_dataset rows so the dashboard runs on live data only."""
    db: Session = SessionLocal()
    try:
        deleted: dict[str, int] = {}

        # Child observations first (FK constraints), then route scaffolding.
        deleted["flight_observations"] = (
            db.query(FlightObservation)
            .filter(FlightObservation.source == "demo_dataset")
            .delete(synchronize_session=False)
        )

        deleted["weather_observations"] = (
            db.query(WeatherObservation)
            .filter(WeatherObservation.source == "demo_dataset")
            .delete(synchronize_session=False)
        )
        deleted["events"] = (
            db.query(Event)
            .filter(Event.source == "demo_dataset")
            .delete(synchronize_session=False)
        )
        deleted["satellite_observations"] = (
            db.query(SatelliteObservation)
            .filter(SatelliteObservation.source == "demo_dataset")
            .delete(synchronize_session=False)
        )

        # Satellites left with no observations at all (demo-only rows; the
        # live connector always commits observations with the satellite).
        db.execute(
            text(
                """
                DELETE FROM satellites
                WHERE id NOT IN (
                    SELECT DISTINCT satellite_id FROM satellite_observations
                )
                """
            )
        )

        # Demo routes whose airports came from the demo scenario only
        # (airports seeded here are real and stay).
        db.execute(
            text(
                """
                DELETE FROM flight_routes
                WHERE id NOT IN (
                    SELECT DISTINCT route_id FROM flight_observations
                    WHERE route_id IS NOT NULL
                )
                """
            )
        )

        db.commit()
        print("Synthetic data purged:", deleted)
        return deleted
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Seed real airports/routes for live ingestion"
    )
    parser.add_argument(
        "--purge-synthetic",
        action="store_true",
        help="Also remove all demo_dataset rows before seeding",
    )
    args = parser.parse_args()

    if args.purge_synthetic:
        purge_synthetic()
    upsert_airports()
