from na_planner.schedule_loader import (
    default_schedule_path,
    latest_schedule_path,
    load_sections,
    offered_codes_by_season,
)


def test_load_sections_groups_by_code_for_season():
    fall = load_sections(default_schedule_path(2026), "fall")
    assert "COMP 1411" in fall                      # real course in the snapshot
    assert all(s.term == "fall" for secs in fall.values() for s in secs)
    spring = load_sections(default_schedule_path(2026), "spring")
    assert all(s.term == "spring" for secs in spring.values() for s in secs)
    # a code offered in fall but not spring appears only in the fall map
    assert set(fall) != set(spring)


def test_offered_codes_by_season_splits_bands():
    seen = offered_codes_by_season(default_schedule_path(2026))
    # COMP 4336 is a fall-only course in this snapshot; COMP 2319 runs both terms.
    assert "COMP 4336" in seen["fall"]
    assert "COMP 4336" not in seen["spring"]
    assert "COMP 2319" in seen["fall"]
    assert "COMP 2319" in seen["spring"]


def test_old_code_aliases_map_to_current_catalog_codes():
    # The 2026 snapshot still uses pre-2026 numbering for two courses:
    # "COMP 4350 Network Security" is COMP 4353 in the 2026 catalog, and
    # "COMP 4353 Data Mining" is COMP 4373. Remap so the timetabler finds them.
    spring = load_sections(default_schedule_path(2026), "spring")
    assert "COMP 4350" not in spring
    assert any(s.title == "Network Security" for s in spring["COMP 4353"])
    assert any(s.title == "Data Mining" for s in spring["COMP 4373"])


def test_offered_codes_by_season_reflect_aliases():
    seen = offered_codes_by_season(default_schedule_path(2026))
    assert "COMP 4373" in seen["spring"]
    assert "COMP 4350" not in seen["spring"]


def test_latest_schedule_path_picks_newest_undergrad_snapshot():
    p = latest_schedule_path()
    assert p is not None
    assert p == default_schedule_path(2026)   # only the 2026 snapshot exists today
