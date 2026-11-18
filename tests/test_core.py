"""Unit tests for Z-UPA's data and calculation layer (no GUI is started)."""
import os

import pytest

import main


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    """Point every data file at a fresh temporary folder for each test."""
    files = {k: str(tmp_path / os.path.basename(v)) for k, v in main.FILES.items()}
    monkeypatch.setattr(main, "FILES", files)
    monkeypatch.setattr(main, "DATA_DIR", str(tmp_path))
    return tmp_path


def write(path, text):
    with open(path, "w") as f:
        f.write(text)


# ---------- authentication ----------
def test_demo_account_is_seeded_and_can_log_in():
    assert main.validate_login("202508134", "12345")
    assert main.get_user_session("202508134")["name"] == "Omar Issam"


@pytest.mark.parametrize("uid,pw", [("202508134", "wrong"), ("999", "12345"), ("", "")])
def test_invalid_credentials_are_rejected(uid, pw):
    assert not main.validate_login(uid, pw)


def test_change_password_updates_only_the_password_field():
    # The old password "1" also appears inside the ID; it must stay untouched.
    write(main.FILES["stu"], "2025001,1,Sara Ali,Year 1,CSAI\n2025002,1,Omar Issam,Year 1,CSAI\n")
    assert main.change_password("2025001", "1", "newpass")
    lines = open(main.FILES["stu"]).read().splitlines()
    assert lines[0] == "2025001,newpass,Sara Ali,Year 1,CSAI"
    assert lines[1] == "2025002,1,Omar Issam,Year 1,CSAI"
    assert main.validate_login("2025001", "newpass")
    assert not main.validate_login("2025001", "1")


def test_change_password_rejects_wrong_old_password():
    write(main.FILES["stu"], "2025001,secret,Sara Ali,Year 1,CSAI\n")
    assert not main.change_password("2025001", "guess", "x")
    assert main.validate_login("2025001", "secret")


# ---------- per-student data isolation ----------
def test_student_ids_are_matched_exactly_not_by_prefix():
    write(main.FILES["grd"], "20250813,CSAI 101,Quiz1,40,2025-01-15\n202508134,CSAI 101,Quiz1,90,2025-01-15\n")
    write(main.FILES["att"], "20250813,CSAI 101,2025-01-10,absent\n202508134,CSAI 101,2025-01-10,present\n")
    grades = main.load_grades("20250813")
    assert [g["grade"] for g in grades] == ["40"]
    assert main.calc_attendance_rate("20250813", "CSAI 101") == 0
    assert main.calc_attendance_rate("202508134", "CSAI 101") == 100


def test_notifications_include_broadcasts_and_own_messages_only():
    write(main.FILES["ntf"], "all,Welcome,2025-01-01\n2025001,For Sara,2025-01-02\n20250012,For someone else,2025-01-03\n")
    msgs = [n["msg"] for n in main.load_notifications("2025001")]
    assert msgs == ["Welcome", "For Sara"]


def test_update_task_status_changes_only_the_exact_task():
    write(main.FILES["tsk"], "all,CSAI 101,Install Python,2025-02-01,pending\n2025001,CSAI 101,Lab,2025-02-02,pending\n2025001,CSAI 101,Lab report,2025-02-03,pending\n")
    main.update_task_status("2025001", "Lab", "completed")
    statuses = {t["task"]: t["status"] for t in main.load_tasks("2025001")}
    assert statuses == {"Install Python": "pending", "Lab": "completed", "Lab report": "pending"}


# ---------- calculations ----------
@pytest.mark.parametrize("grades,expected", [
    ([], 0.0),
    ([{"grade": "100"}], 4.0),
    ([{"grade": "85"}, {"grade": "78"}], 3.26),
    ([{"grade": "0"}], 0.0),
])
def test_calc_gpa(grades, expected):
    assert main.calc_gpa(grades) == expected


@pytest.mark.parametrize("user,correct,expected", [
    (["A", "B", "C"], ["A", "B", "C"], 100),
    (["A", "X", "C"], ["A", "B", "C"], 66),
    (["X"], ["A"], 0),
    ([], [], 0),
])
def test_calc_score(user, correct, expected):
    assert main.calc_score(user, correct) == expected


def test_attendance_rate_without_records_defaults_to_full():
    write(main.FILES["att"], "")
    assert main.calc_attendance_rate("2025001", "CSAI 101") == 100


# ---------- courses and reports ----------
def test_filter_and_search_courses():
    write(main.FILES["crs"], "CSAI 101,Python,Dr. A,Eng. B,Year 1\nCSAI 201,Data Structures,Dr. C,Eng. D,Year 2\n")
    assert [c["code"] for c in main.filter_courses("Year 1", "CSAI")] == ["CSAI 101"]
    assert [c["code"] for c in main.search_course("data")] == ["CSAI 201"]
    assert [c["code"] for c in main.search_course("csai")] == ["CSAI 101", "CSAI 201"]


def test_quiz_results_export_to_report(isolated_data):
    main.save_result("2025001", "CSAI 101", 80)
    main.save_result("20250012", "CSAI 101", 50)
    path = main.export_report("2025001")
    assert path == str(isolated_data / "Report_2025001.txt")
    lines = open(path).read().splitlines()
    assert len(lines) == 1 and lines[0].startswith("2025001,CSAI 101,80,")


def test_export_report_without_results_returns_none():
    assert main.export_report("2025001") is None

