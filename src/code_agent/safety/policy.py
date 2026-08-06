"""
safety/policy.py — базовые уровни риска по умолчанию для известных инструментов
(конкретные инструменты могут переопределять через get_risk на основе аргументов —
это только дефолтная таблица-справочник).
"""
from code_agent.models import RiskLevel

DEFAULT_RISK_TABLE: dict[str, RiskLevel] = {
    "filesystem.list_files": RiskLevel.SAFE,
    "filesystem.read_file": RiskLevel.SAFE,
    "search.search_text": RiskLevel.SAFE,
    "tests.run": RiskLevel.SAFE,
    "git.status": RiskLevel.SAFE,
    "git.diff": RiskLevel.SAFE,
    "filesystem.write_file": RiskLevel.REVIEW,
    "code.apply_patch": RiskLevel.REVIEW,
}
