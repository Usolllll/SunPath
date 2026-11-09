"""Reference coordinates are separate from synthetic admission records; no live geocoding."""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def locations():
    return json.loads((Path(__file__).resolve().parents[1] / 'data/university_locations.json').read_text(encoding='utf-8'))


def university_locations(items):
    schools = {}
    for group in items:
        university = group['university']
        school = schools.setdefault(university['id'], {
            **university,
            'location': locations().get(university['name']),
            'group_ids': [], 'group_count': 0,
        })
        school['group_ids'].append(group['id'])
        school['group_count'] += 1
    return list(schools.values())
