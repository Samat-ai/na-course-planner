from na_planner.models.catalog import Course, Program, RequirementGroup
from na_planner.models.preferences import StudentPreferences
from na_planner.models.schedule import Section, Weekday
from na_planner.timetabler import timetable_term


def _prog(codes_credits, difficulty=None):
    courses = {c: Course(code=c, credits=cr,
                         difficulty=(difficulty or {}).get(c))
               for c, cr in codes_credits.items()}
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=list(courses))]
    return Program(code="X", name="X", catalog_year=2026,
                   total_credits_required=99, courses=courses, groups=groups)


def _sec(code, sec, days, start, end):
    return Section(course_code=code, section=sec, term="fall",
                   days=days, start_min=start, end_min=end)


def test_substitutes_conflicting_course_and_stays_conflict_free():
    prog = _prog({"A 1300": 3, "B 1300": 3, "C 1300": 3})
    prefs = StudentPreferences(target_credits=6.0, max_load=6.0)
    secs = {
        "A 1300": [_sec("A 1300", "1", [Weekday.MON], 600, 690)],
        "B 1300": [_sec("B 1300", "1", [Weekday.MON], 660, 750)],  # clashes with A
        "C 1300": [_sec("C 1300", "1", [Weekday.TUE], 600, 690)],  # fits with A
    }
    term = timetable_term(["A 1300", "B 1300", "C 1300"], prog, prefs, secs)
    codes = {c.code for c in term.courses}
    assert "A 1300" in codes                 # rank-1 never dropped
    assert "B 1300" not in codes             # substituted away (clashes with A)
    assert "C 1300" in codes                 # fits alongside A
    assert all(c.section is not None for c in term.courses)


def test_prefers_compact_week_among_equal_inclusion():
    prog = _prog({"A 1300": 3})
    prefs = StudentPreferences(target_credits=3.0, max_load=3.0)
    secs = {"A 1300": [
        _sec("A 1300", "1", [Weekday.MON, Weekday.WED, Weekday.FRI], 600, 660),
        _sec("A 1300", "2", [Weekday.TUE, Weekday.THU], 600, 660),
    ]}
    term = timetable_term(["A 1300"], prog, prefs, secs)
    chosen = term.courses[0].section
    assert chosen.section == "2"             # 2 campus days beats 3


def test_compact_week_off_skips_day_minimization():
    # Same MWF vs TuTh sections, both start 600. With compact_week off, day count is
    # ignored and the tiebreak falls to earliest start then lowest section -> section "1".
    prog = _prog({"A 1300": 3})
    prefs = StudentPreferences(target_credits=3.0, max_load=3.0, compact_week=False)
    secs = {"A 1300": [
        _sec("A 1300", "1", [Weekday.MON, Weekday.WED, Weekday.FRI], 600, 660),
        _sec("A 1300", "2", [Weekday.TUE, Weekday.THU], 600, 660),
    ]}
    term = timetable_term(["A 1300"], prog, prefs, secs)
    assert term.courses[0].section.section == "1"


def test_course_with_no_section_is_kept_and_flagged():
    prog = _prog({"A 1300": 3})
    prefs = StudentPreferences(target_credits=3.0, max_load=3.0)
    term = timetable_term(["A 1300"], prog, prefs, sections_by_code={})
    pc = term.courses[0]
    assert pc.code == "A 1300"
    assert pc.section is not None and pc.section.note is not None


def test_under_fill_when_no_conflict_free_full_term():
    prog = _prog({"A 1300": 3, "B 1300": 3})
    prefs = StudentPreferences(target_credits=6.0, max_load=6.0)
    secs = {
        "A 1300": [_sec("A 1300", "1", [Weekday.MON], 600, 690)],
        "B 1300": [_sec("B 1300", "1", [Weekday.MON], 630, 720)],  # clashes
    }
    term = timetable_term(["A 1300", "B 1300"], prog, prefs, secs)
    assert len(term.courses) == 1            # conflict-free but under target
    assert term.courses[0].code == "A 1300"  # rank-1 kept


def test_bench_is_bounded_and_fast():
    prog = _prog({f"C {1300 + i}": 3 for i in range(40)})
    prefs = StudentPreferences(target_credits=15.0, max_load=19.0)
    secs = {c: [_sec(c, "1", [Weekday.MON], 600 + i * 5, 640 + i * 5)]
            for i, c in enumerate(prog.courses)}
    term = timetable_term(list(prog.courses), prog, prefs, secs)
    assert term.total_credits <= 15.0
