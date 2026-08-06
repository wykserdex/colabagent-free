"""
infrastructure/output_limiter.py — обрезка вывода
"""


def limit_output(text: str, maximum: int = 30000) -> str:
    if len(text) <= maximum:
        return text
    half = maximum // 2
    return text[:half] + "\n... ОБРЕЗАНО ...\n" + text[-half:]
