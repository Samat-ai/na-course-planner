from na_planner.models.schedule import Section, SectionInfo, Weekday


def test_section_async_flag():
    lecture = Section(course_code="COMP 1411", section="1", term="fall",
                      days=[Weekday.MON, Weekday.WED], start_min=600, end_min=690)
    online = Section(course_code="PHIL 1312", section="1", term="fall",
                     meeting_type="OF")
    assert lecture.is_async is False
    assert online.is_async is True


def test_section_info_from_section_carries_fields_and_note():
    s = Section(course_code="COMP 1411", section="2", term="fall",
                days=[Weekday.TUE], start_min=630, end_min=720, room="815",
                professor="Doe", meeting_type="IP")
    info = SectionInfo.from_section(s, note="confirm offering")
    assert info.section == "2"
    assert info.days == [Weekday.TUE]
    assert info.start_min == 630 and info.end_min == 720
    assert info.room == "815" and info.meeting_type == "IP"
    assert info.note == "confirm offering"
