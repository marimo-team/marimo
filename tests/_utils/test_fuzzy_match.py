# Copyright 2025 Marimo. All rights reserved.


from marimo._utils.fuzzy_match import compile_regex, is_fuzzy_match


def test_compile_regex_valid_pattern():
    """Test _compile_regex with valid regex pattern."""
    pattern, is_regex = compile_regex("^user.*")

    assert pattern is not None
    assert is_regex is True
    assert pattern.search("users") is not None
    assert pattern.search("orders") is None


def test_compile_regex_invalid_pattern():
    """Test _compile_regex with invalid regex pattern."""
    pattern, is_regex = compile_regex("[invalid")

    assert pattern is None
    assert is_regex is False


def test_compile_regex_simple_text():
    """Test _compile_regex with simple text (valid regex)."""
    pattern, is_regex = compile_regex("user")

    assert pattern is not None
    assert is_regex is True
    assert pattern.search("users") is not None
    assert pattern.search("orders") is None


def test_is_fuzzy_match_with_regex():
    """Test is_fuzzy_match with compiled regex pattern."""
    pattern, is_regex = compile_regex("^user.*")

    assert is_fuzzy_match("^user.*", "users", pattern, is_regex) is True
    assert is_fuzzy_match("^user.*", "orders", pattern, is_regex) is False


def test_is_fuzzy_match_without_regex():
    """Test is_fuzzy_match with invalid regex (fallback to substring)."""
    pattern, is_regex = compile_regex("[invalid")

    assert is_fuzzy_match("[invalid", "users", pattern, is_regex) is False
    assert is_fuzzy_match("[invalid", "[invalid", pattern, is_regex) is True


def test_is_fuzzy_match_case_insensitive():
    """Test that matching is case insensitive."""
    pattern, is_regex = compile_regex("USER")

    assert is_fuzzy_match("USER", "users", pattern, is_regex) is True
    assert is_fuzzy_match("USER", "USERS", pattern, is_regex) is True
    assert is_fuzzy_match("USER", "orders", pattern, is_regex) is False
