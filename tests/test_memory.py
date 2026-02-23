from unittest.mock import MagicMock

import pytest

from src.runner import calculate_max_workers, parse_mem_string


def test_parse_megabytes() -> None:
    assert parse_mem_string("512m") == 512 * 1024 * 1024


def test_parse_gigabytes() -> None:
    assert parse_mem_string("1g") == 1024 * 1024 * 1024


def test_parse_uppercase() -> None:
    assert parse_mem_string("256M") == 256 * 1024 * 1024


def test_parse_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_mem_string("abc")


def test_max_workers_basic() -> None:
    client = MagicMock()
    client.info.return_value = {"MemTotal": 4 * 1024 * 1024 * 1024}
    assert calculate_max_workers(client, "512m") == 6


def test_max_workers_minimum_one() -> None:
    client = MagicMock()
    client.info.return_value = {"MemTotal": 256 * 1024 * 1024}
    assert calculate_max_workers(client, "512m") == 1
