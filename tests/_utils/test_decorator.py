# Assuming the debounce decorator is defined in a file named debounce.py
import time

from marimo._utils.debounce import debounce

# A simple function for testing purposes
call_count = 0


def test_debounce_within_period():
    @debounce(wait_time=1.5)
    def my_function():
        global call_count
        call_count += 1

    global call_count
    call_count = 0  # Reset the counter before the test

    my_function()  # Call the function for the first time
    assert call_count == 1

    time.sleep(0.1)  # Wait less than the debounce period
    my_function()  # Attempt to call the function again
    assert call_count == 1


def test_debounce_after_period():
    @debounce(wait_time=0.1)
    def my_function():
        global call_count
        call_count += 1

    global call_count
    call_count = 0  # Reset the counter before the test

    my_function()  # Call the function for the first time
    assert call_count == 1

    time.sleep(0.4)  # Wait more than the debounce period
    my_function()  # Attempt to call the function again
    assert call_count == 2
