import subprocess


def test_script():
    p = subprocess.run(
        ["python", "tests/_runtime/script_data/script_exception.py"],
        capture_output=True,
    )
    assert p.returncode == 1

    result = p.stderr.decode()
    assert "NameError: name 'y' is not defined" in result
    assert (
        "/tests/_runtime/script_data/script_exception.py\", line 10" in result
    )
    assert "y = y/x" in result
