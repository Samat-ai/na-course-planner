from na_planner.schedule_loader import default_schedule_path, load_sections


def test_load_sections_groups_by_code_for_season():
    fall = load_sections(default_schedule_path(2026), "fall")
    assert "COMP 1411" in fall                      # real course in the snapshot
    assert all(s.term == "fall" for secs in fall.values() for s in secs)
    spring = load_sections(default_schedule_path(2026), "spring")
    assert all(s.term == "spring" for secs in spring.values() for s in secs)
    # a code offered in fall but not spring appears only in the fall map
    assert set(fall) != set(spring)
