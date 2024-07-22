import subprocess


def test_script():
    p = subprocess.run(
        ["python", "tests/_runtime/script_data/script_exception.py"],
        capture_output=True,
    )
    assert p.returncode == 1

    result = p.stderr.decode()
    assert "NameError: name 'y' is not defined" in result
    assert 'tests/_runtime/script_data/script_exception.py", line 10' in result
    assert "y = y / x" in result


def test_script_with_output():
    p = subprocess.run(
        [
            "python",
            "tests/_runtime/script_data/script_exception_with_output.py",
        ],
        capture_output=True,
    )
    assert p.returncode == 1

    result = p.stderr.decode()
    assert "NameError: name 'y' is not defined" in result
    assert (
        'tests/_runtime/script_data/script_exception_with_output.py"'
        + ", line 10"
        in result
    )
    assert "y / x" in result


def test_script_with_imported_file():
    p = subprocess.run(
        [
            "python",
            "tests/_runtime/script_data/script_exception_with_imported_function.py",
        ],
        capture_output=True,
    )
    assert p.returncode == 1

    result = p.stderr.decode()
    assert "ZeroDivisionError: division by zero" in result
    assert 'tests/_runtime/script_data/func.py", line 3' in result
    assert (
        'tests/_runtime/script_data/script_exception_with_imported_function.py"'
        + ", line 11"
        in result
    )
    assert "y = y / x" in result
