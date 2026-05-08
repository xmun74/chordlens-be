"""Structured logger 설정.

기존 print 호출을 점진적으로 교체하기 위한 표준 logger를 제공한다.
포맷은 stdout 텍스트 라인 — `<ts> <level> <name> <message>`.
"""
import logging
import sys


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
