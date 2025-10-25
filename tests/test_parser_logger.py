import logging

from click import BadParameter
from pytest import raises

from typerplus.parser.logger import LoggerParser


def test_logger_value_str_num_coerce():
    parser = LoggerParser()
    logger = parser.convert("3", None, None)
    assert logger.level == logging.DEBUG
    assert logger.name == "typerplus"

    logger = parser.convert(2, None, None)
    assert logger.level == logging.INFO

    logger = parser.convert(1, None, None)
    assert logger.level == logging.WARNING

    logger = parser.convert(0, None, None)
    assert logger.level == logging.ERROR


def test_logger_value_str_large_coerce():
    parser = LoggerParser()
    logger = parser.convert("10", None, None)
    assert logger.level == logging.DEBUG


def test_logger_value_str_coerce_level_name():
    parser = LoggerParser()
    logger = parser.convert("INFO", None, None)
    assert logger.level == logging.INFO

    logger = parser.convert("warning", None, None)
    assert logger.level == logging.WARNING


def test_logger_value_str_coerce_unknown():
    parser = LoggerParser()
    with raises(BadParameter):
        _ = parser.convert("XYZ", None, None)


def test_logger_value_coerce_obj_fail():
    parser = LoggerParser()
    with raises(BadParameter):
        _ = parser.convert(object(), None, None)


def test_logger_value_coerce_empty_string():
    parser = LoggerParser()
    with raises(BadParameter):
        _ = parser.convert(" ", None, None)


def test_logger_value_coerce_logger():
    parser = LoggerParser()
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.ERROR)

    new_logger = parser.convert(logger, None, None)
    assert new_logger.level == logging.ERROR
