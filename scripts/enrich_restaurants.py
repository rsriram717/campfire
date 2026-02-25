"""
Backfill missing metadata (primary_type, price_level, rating, etc.) for
Restaurant records that predate the rich schema migration.

Fetches data from Google Places get_details() for every record where
primary_type IS NULL and place_id starts with 'ChIJ' (valid Google IDs).

Skips:
  - Yelp-style slugs (no ChIJ prefix)
  - campfire_ai provider records
  - Any place where Google returns no data

Usage:
    venv/bin/python scripts/enrich_restaurants.py
    venv/bin/python scripts/enrich_restaurants.py --dry-run
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app import app, db
from models import Restaurant
from services.google_service import GooglePlacesService

logging.basicConfig(level=logging.INFO, format="%(message)s")

def run(dry_run=False):
    service = GooglePlacesService()

    with app.app_context():
        targets = Restaurant.query.filter(
            Restaurant.primary_type.is_(None),
            Restaurant.provider == 'google',
            Restaurant.place_id.like('ChIJ%'),
        ).order_by(Restaurant.id).all()

        print(f"Found {len(targets)} restaurants to enrich{' (dry run)' if dry_run else ''}.\n")

        ok = skipped = failed = 0

        for r in targets:
            details = service.get_details(r.place_id)

            if not details or not details.get('primary_type'):
                print(f"  SKIP  [{r.id}] {r.name} — no primary_type returned")
                skipped += 1
                continue

            if dry_run:
                print(
                    f"  DRY   [{r.id}] {r.name}\n"
                    f"         type={details.get('primary_type')}  "
                    f"price={details.get('price_level')}  "
                    f"rating={details.get('rating')}"
                )
                ok += 1
                continue

            r.primary_type       = details.get('primary_type')
            r.price_level        = details.get('price_level')        or r.price_level
            r.rating             = details.get('rating')             or r.rating
            r.user_rating_count  = details.get('user_rating_count')  or r.user_rating_count
            r.editorial_summary  = details.get('editorial_summary')  or r.editorial_summary
            r.serves_dine_in     = details.get('serves_dine_in')
            r.serves_takeout     = details.get('serves_takeout')
            r.serves_delivery    = details.get('serves_delivery')
            r.reservable         = details.get('reservable')
            r.last_enriched_at   = datetime.utcnow()

            try:
                db.session.commit()
                print(
                    f"  OK    [{r.id}] {r.name}\n"
                    f"         type={r.primary_type}  "
                    f"price={r.price_level}  "
                    f"rating={r.rating}"
                )
                ok += 1
            except Exception as e:
                db.session.rollback()
                print(f"  ERROR [{r.id}] {r.name} — {e}")
                failed += 1

        print(f"\nDone. ok={ok}  skipped={skipped}  failed={failed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Fetch data but do not write to DB")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
