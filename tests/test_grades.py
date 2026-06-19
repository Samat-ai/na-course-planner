from na_planner.grades import Grade, is_passing, meets_minimum


def test_letter_ordering_via_points():
    assert meets_minimum(Grade.A, Grade.C) is True
    assert meets_minimum(Grade.C, Grade.C) is True
    assert meets_minimum(Grade.C_MINUS, Grade.C) is False
    assert meets_minimum(Grade.D, Grade.C) is False


def test_passing():
    assert is_passing(Grade.D) is True      # passing for the course
    assert is_passing(Grade.P) is True
    assert is_passing(Grade.F) is False
    assert is_passing(Grade.W) is False
    assert is_passing(Grade.WIP) is False   # in progress is not yet passed


def test_meets_minimum_rejects_non_letter_earned():
    # A pass/in-progress grade cannot satisfy a specific letter minimum
    assert meets_minimum(Grade.P, Grade.C) is False
    assert meets_minimum(Grade.WIP, Grade.C) is False
