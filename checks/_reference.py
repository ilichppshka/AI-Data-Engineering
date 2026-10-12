"""Эталоны для проверок.

Содержимое закодировано намеренно: иначе решения заданий лежали бы рядом
с самими заданиями. Читаемый исходник – tools/reference_src.py, пересборка –
python tools/build_reference.py
"""

_DATA = (
    "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"
    "QfI/ieCNCw=="
)

import base64
import zlib

exec(compile(zlib.decompress(base64.b64decode(_DATA)).decode("utf-8"),
             "<reference>", "exec"))
