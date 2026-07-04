from na_planner.roadmap import restrict_to_season

# A snapshot signal: FALL 1000 runs fall only, SPRING 1000 spring only,
# BOTH 1000 both terms. NEITHER 1000 appears in no band (no evidence).
SEEN = {"fall": {"FALL 1000", "BOTH 1000"}, "spring": {"SPRING 1000", "BOTH 1000"}}


def test_removes_other_season_only_course():
    # Planning a spring term: a fall-only course must be dropped.
    out = restrict_to_season(["FALL 1000", "BOTH 1000", "SPRING 1000"], "spring", SEEN)
    assert out == ["BOTH 1000", "SPRING 1000"]


def test_keeps_both_season_and_target_season_courses():
    out = restrict_to_season(["BOTH 1000", "FALL 1000"], "fall", SEEN)
    assert out == ["BOTH 1000", "FALL 1000"]


def test_keeps_courses_with_no_signal():
    # NEITHER 1000 is in no band -> no evidence it's off-season -> keep it (Option 1 rule).
    out = restrict_to_season(["NEITHER 1000", "FALL 1000"], "spring", SEEN)
    assert out == ["NEITHER 1000"]


def test_no_band_for_season_is_a_no_op():
    # If the snapshot has no data for the target season, filter nothing.
    out = restrict_to_season(["FALL 1000", "SPRING 1000"], "summer", SEEN)
    assert out == ["FALL 1000", "SPRING 1000"]


def test_empty_signal_is_a_no_op():
    out = restrict_to_season(["FALL 1000", "SPRING 1000"], "spring", {})
    assert out == ["FALL 1000", "SPRING 1000"]
