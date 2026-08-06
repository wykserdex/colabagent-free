"""
infrastructure/atomic_write.py — атомарная запись файла: пишем во временный файл
рядом, потом os.replace (атомарная операция на уровне ФС). Гарантирует что при
краше процесса ПОСРЕДИ записи целевой файл остаётся либо старым, либо новым,
никогда не битым наполовину.
"""
import os
from pathlib import Path


def atomic_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding=encoding, newline="\n") as f:
        f.write(content)
    os.replace(tmp_path, path)
