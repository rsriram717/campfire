"""
Benchmark script for the ranking algorithm.

Runs 3 fixed scenarios end-to-end, including optional live Haiku API calls.
Results saved to scripts/benchmark_results/ as JSON for before/after comparison.

Usage:
    venv/bin/python scripts/benchmark_ranking.py --tag baseline
    venv/bin/python scripts/benchmark_ranking.py --tag new
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from openai_example import rank_candidates, build_taste_profile
try:
    from openai_example import score_candidates, mmr_select
    HAS_NEW_PIPELINE = True
except ImportError:
    HAS_NEW_PIPELINE = False

# ---------------------------------------------------------------------------
# Shared candidate pool helpers
# ---------------------------------------------------------------------------

def _c(name, primary_type, price_level, rating, categories=None, place_id=None, editorial_summary=None):
    return {
        "place_id": place_id or name.lower().replace(" ", "_"),
        "name": name,
        "primary_type": primary_type,
        "price_level": price_level,
        "rating": rating,
        "categories": categories or [],
        "editorial_summary": editorial_summary or "",
        "address": "123 Main St",
        "_is_revisit": False,
    }


def _dislike_obj(primary_type):
    m = MagicMock()
    m.primary_type = primary_type
    return m


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIO_A = {
    "name": "Scenario A — Session taqueria, no history",
    "taste_profile": {
        "top_cuisine_types": ["mexican_restaurant"],
        "preferred_price_level": "PRICE_LEVEL_INEXPENSIVE",
        "min_rating": 4.4,
    },
    "disliked_objs": [],
    "candidates": [
        _c("Alinea",          "american_restaurant",  "PRICE_LEVEL_VERY_EXPENSIVE", 4.9),
        _c("Nobu",            "sushi_restaurant",     "PRICE_LEVEL_EXPENSIVE",      4.8),
        _c("Eataly",          "italian_restaurant",   "PRICE_LEVEL_EXPENSIVE",      4.7),
        _c("Girl & Goat",     "american_restaurant",  "PRICE_LEVEL_MODERATE",       4.6),
        _c("Taqueria Chingon","mexican_restaurant",   "PRICE_LEVEL_INEXPENSIVE",    4.6),
        _c("El Torito",       "mexican_restaurant",   "PRICE_LEVEL_INEXPENSIVE",    4.4),
        _c("Pequod's Pizza",  "pizza_restaurant",     "PRICE_LEVEL_MODERATE",       4.5),
        _c("Frontera Grill",  "mexican_restaurant",   "PRICE_LEVEL_MODERATE",       4.5),
        _c("Longman & Eagle", "bar",                  "PRICE_LEVEL_MODERATE",       4.3),
        _c("Lou Malnati's",   "pizza_restaurant",     "PRICE_LEVEL_INEXPENSIVE",    4.4),
    ],
    "liked_names": ["Taqueria Moran"],
    "disliked_names": [],
    "city": "Chicago",
    "neighborhood": None,
    "restaurant_types": None,
    "alpha": 0.9,
    "revisit_weight": 0.0,
    "liked_restaurant_objs": [],
    "input_restaurant_objs": [],
}

SCENARIO_B = {
    "name": "Scenario B — History-heavy Italian lover, sushi dislikes",
    "taste_profile": {
        "top_cuisine_types": ["italian_restaurant"],
        "preferred_price_level": "PRICE_LEVEL_MODERATE",
        "min_rating": 4.4,
    },
    "disliked_objs": [
        _dislike_obj("sushi_restaurant"),
        _dislike_obj("sushi_restaurant"),
    ],
    "candidates": [
        _c("Nobu",             "sushi_restaurant",     "PRICE_LEVEL_EXPENSIVE",  4.9),
        _c("Juno Sushi",       "sushi_restaurant",     "PRICE_LEVEL_MODERATE",   4.7),
        _c("Spacca Napoli",    "italian_restaurant",   "PRICE_LEVEL_MODERATE",   4.7),
        _c("Monteverde",       "italian_restaurant",   "PRICE_LEVEL_MODERATE",   4.6),
        _c("Eataly",           "italian_restaurant",   "PRICE_LEVEL_EXPENSIVE",  4.5),
        _c("Au Cheval",        "american_restaurant",  "PRICE_LEVEL_MODERATE",   4.5),
        _c("Avec",             "mediterranean_restaurant", "PRICE_LEVEL_MODERATE", 4.5),
        _c("Big Star",         "mexican_restaurant",   "PRICE_LEVEL_INEXPENSIVE",4.4),
        _c("Dusek's",          "american_restaurant",  "PRICE_LEVEL_MODERATE",   4.3),
        _c("Publican",         "american_restaurant",  "PRICE_LEVEL_MODERATE",   4.4),
    ],
    "liked_names": ["Pasta d'Arte", "Trattoria Roma"],
    "disliked_names": ["Nobu", "Juno Sushi"],
    "city": "Chicago",
    "neighborhood": None,
    "restaurant_types": None,
    "alpha": 0.3,
    "revisit_weight": 0.0,
    "liked_restaurant_objs": [],
    "input_restaurant_objs": [],
}

SCENARIO_C = {
    "name": "Scenario C — No cuisine signal, mixed pool (regression check)",
    "taste_profile": {
        "top_cuisine_types": [],
        "preferred_price_level": "PRICE_LEVEL_EXPENSIVE",
        "min_rating": 4.6,
    },
    "disliked_objs": [],
    "candidates": [
        _c("Alinea",          "american_restaurant",  "PRICE_LEVEL_VERY_EXPENSIVE", 4.9),
        _c("Smyth",           "american_restaurant",  "PRICE_LEVEL_EXPENSIVE",      4.8),
        _c("Oriole",          "american_restaurant",  "PRICE_LEVEL_VERY_EXPENSIVE", 4.7),
        _c("Moody Tongue",    "american_restaurant",  "PRICE_LEVEL_EXPENSIVE",      4.6),
        _c("Temporis",        "american_restaurant",  "PRICE_LEVEL_EXPENSIVE",      4.5),
        _c("Boka",            "american_restaurant",  "PRICE_LEVEL_EXPENSIVE",      4.5),
        _c("Elske",           "american_restaurant",  "PRICE_LEVEL_EXPENSIVE",      4.4),
        _c("Longman & Eagle", "bar",                  "PRICE_LEVEL_MODERATE",       4.3),
        _c("Au Cheval",       "american_restaurant",  "PRICE_LEVEL_MODERATE",       4.5),
        _c("Girl & Goat",     "american_restaurant",  "PRICE_LEVEL_MODERATE",       4.6),
    ],
    "liked_names": [],
    "disliked_names": [],
    "city": "Chicago",
    "neighborhood": None,
    "restaurant_types": None,
    "alpha": 0.7,
    "revisit_weight": 0.0,
    "liked_restaurant_objs": [],
    "input_restaurant_objs": [],
}

SCENARIOS = [SCENARIO_A, SCENARIO_B, SCENARIO_C]

# ---------------------------------------------------------------------------
# Rating-sort baseline selection (old behavior)
# ---------------------------------------------------------------------------

def old_selection(candidates, n=3):
    """Simulate old behavior: sort by rating, take top n."""
    sorted_c = sorted(candidates, key=lambda c: c.get("rating") or 0, reverse=True)
    return sorted_c[:n]


# ---------------------------------------------------------------------------
# Main benchmark runner
# ---------------------------------------------------------------------------

def run_scenario(scenario, tag, use_llm, n_runs=3):
    candidates = scenario["candidates"]
    taste_profile = scenario["taste_profile"]
    disliked_objs = scenario["disliked_objs"]

    print(f"\n{'='*60}")
    print(f"  {scenario['name']}")
    print(f"{'='*60}")

    # --- Old selection (rating sort) ---
    old_picks = old_selection(candidates)
    print("\nOLD (rating sort):")
    for i, c in enumerate(old_picks, 1):
        print(f"  {i}. {c['name']} ({c.get('primary_type','?')}, ★{c.get('rating','?')})")

    # --- New selection (score + MMR) ---
    if HAS_NEW_PIPELINE:
        try:
            scored = score_candidates(candidates, taste_profile, disliked_objs)
            new_picks = mmr_select(scored, n=3)
            print("\nNEW (score+MMR):")
            for i, c in enumerate(new_picks, 1):
                print(f"  {i}. {c['name']} ({c.get('primary_type','?')}, ★{c.get('rating','?')}, score={c.get('_score', 0):.3f})")
        except Exception as e:
            print(f"\nNEW selection failed: {e}")
            new_picks = old_picks
            scored = []
    else:
        print("\nNEW (score+MMR): not available — score_candidates/mmr_select not yet implemented")
        new_picks = old_picks
        scored = []

    llm_outputs = []

    # --- LLM explanation runs ---
    if use_llm:
        print(f"\nLLM runs (n={n_runs}):")
        for run_i in range(1, n_runs + 1):
            try:
                call_kwargs = dict(
                    taste_profile=taste_profile,
                    candidates=candidates,
                    liked_names=scenario["liked_names"],
                    disliked_names=scenario["disliked_names"],
                    city=scenario["city"],
                    neighborhood=scenario.get("neighborhood"),
                    restaurant_types=scenario.get("restaurant_types"),
                    num_recommendations=3,
                    liked_restaurant_objs=scenario.get("liked_restaurant_objs", []),
                    input_restaurant_objs=scenario.get("input_restaurant_objs", []),
                    alpha=scenario["alpha"],
                    revisit_weight=scenario["revisit_weight"],
                )
                if HAS_NEW_PIPELINE:
                    call_kwargs["disliked_restaurant_objs"] = disliked_objs
                results = rank_candidates(**call_kwargs)
                run_output = [
                    f"{r['name']}: {r.get('reason','')} — {r.get('description','')}"
                    for r in results
                ]
                llm_outputs.append(run_output)
                print(f"\n  Run {run_i}:")
                for line in run_output:
                    print(f"    {line}")
            except Exception as e:
                print(f"  Run {run_i} failed: {e}")
                llm_outputs.append([f"ERROR: {e}"])
    else:
        print("\n(LLM step skipped — ANTHROPIC_API_KEY not set)")

    return {
        "scenario": scenario["name"],
        "old_selection": [
            {"name": c["name"], "primary_type": c.get("primary_type"), "rating": c.get("rating")}
            for c in old_picks
        ],
        "new_selection": [
            {
                "name": c["name"],
                "primary_type": c.get("primary_type"),
                "rating": c.get("rating"),
                "score": round(c.get("_score", 0), 4),
            }
            for c in new_picks
        ],
        "llm_outputs": llm_outputs,
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark ranking algorithm")
    parser.add_argument("--tag", default="run", help="Tag for output file (e.g. baseline, new)")
    parser.add_argument("--runs", type=int, default=3, help="LLM runs per scenario")
    args = parser.parse_args()

    use_llm = bool(os.getenv("ANTHROPIC_API_KEY"))
    if not use_llm:
        print("ANTHROPIC_API_KEY not set — running selection benchmark only (no LLM calls)")

    all_results = []
    for scenario in SCENARIOS:
        result = run_scenario(scenario, args.tag, use_llm, n_runs=args.runs)
        all_results.append(result)

    output_path = Path(__file__).parent / "benchmark_results" / f"{args.tag}_{date.today()}.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
