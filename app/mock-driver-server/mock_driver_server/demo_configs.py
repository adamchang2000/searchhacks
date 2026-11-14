"""Seed reproducible demo scenarios without replacing saved configs.

Run from app/mock-driver-server: uv run python -m mock_driver_server.demo_configs
"""
import json
from pathlib import Path

DESCRIPTIONS = {
    "Category crossover · Exa shopping / Tavily travel": "Exa wins on shopping; Tavily wins on travel. Tests whether routing learns a different winner for each category.",
    "Three specialists · Brave / Parallel / Exa": "Brave wins shopping, Parallel wins travel, and Exa wins computer science. Equal traffic tests three independent category preferences.",
    "Close race · Exa vs Tavily": "Exa has a small edge in shopping; Tavily has a small edge in travel. Tests learning when the difference is only five percentage points.",
    "Clear winner · Exa baseline": "Exa has a large advantage in every category. A baseline for checking that routing converges toward an obvious winner.",
}

OUTCOMES = ("purchase_conversion", "user_confirmed_outcome", "user_stopped_following_up")


def demo_configs(providers):
    corpus = {c["id"]: c for c in json.loads(Path(__file__).with_name("query_corpus.json").read_text())}
    def make(name, categories, strengths):
        return {
            "name": name,
            "description": DESCRIPTIONS[name],
            "config": {
                "total_queries": None,
                "rate_per_second": 5,
                "providers": list(providers),
                "categories": [{**corpus[c], "weight": weight} for c, weight in categories],
                "success_rates": {
                    str(category): {
                        provider: dict(zip(OUTCOMES, strengths.get(category, {}).get(provider, (.08, .15, .1))))
                        for provider in providers
                    }
                    for category, _ in categories
                },
            },
        }
    return [
        make("Category crossover · Exa shopping / Tavily travel", [(18, 1), (67, 1)], {
            18: {"exa": (.8, .9, .75), "tavily": (.2, .3, .25)},
            67: {"exa": (.2, .3, .25), "tavily": (.8, .9, .75)},
        }),
        make("Three specialists · Brave / Parallel / Exa", [(18, 1), (67, 1), (1227, 1)], {
            18: {"brave": (.8, .9, .75), "parallel": (.3, .4, .3), "exa": (.3, .4, .3)},
            67: {"parallel": (.8, .9, .75), "brave": (.3, .4, .3), "exa": (.3, .4, .3)},
            1227: {"exa": (.8, .9, .75), "brave": (.3, .4, .3), "parallel": (.3, .4, .3)},
        }),
        make("Close race · Exa vs Tavily", [(18, 1), (67, 1)], {
            18: {"exa": (.55, .65, .5), "tavily": (.5, .6, .45)},
            67: {"exa": (.5, .6, .45), "tavily": (.55, .65, .5)},
        }),
        make("Clear winner · Exa baseline", [(18, 1), (67, 1), (1227, 1)], {
            category: {"exa": (.85, .95, .8)} for category in (18, 67, 1227)
        }),
    ]


def main():
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mock_driver_server.settings")
    import django
    django.setup()
    from uuid import uuid4
    from mock_driver_server.sim import PROVIDERS, db, now, validate
    with db() as conn:
        names = {row["name"] for row in conn.execute("SELECT name FROM saved_sim_configs")}
        for item in demo_configs(PROVIDERS):
            validate(item["config"])
            if item["name"] not in names:
                conn.execute("INSERT INTO saved_sim_configs (id,name,created_at,body,description) VALUES (?,?,?,?,?)",
                             (str(uuid4()), item["name"], now(), json.dumps(item["config"]), item["description"]))
                print("Created: " + item["name"])
            else:
                conn.execute("UPDATE saved_sim_configs SET description=? WHERE name=? AND description=''",
                             (item["description"], item["name"]))
                print("Updated description: " + item["name"])


if __name__ == "__main__":
    main()
