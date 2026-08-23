"""harness 自身のテスト（pytest）の共通設定。

`harness/hooks/lib` と `harness/scripts` を import 可能にする。hooks 側は依存ゼロ
（標準ライブラリのみ）を厳守しているため、テストからも素の import で読み込める。
"""
from __future__ import annotations

import pathlib
import sys

HARNESS_ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO_ROOT = HARNESS_ROOT.parent

for path in (HARNESS_ROOT / "hooks" / "lib", HARNESS_ROOT / "scripts", HARNESS_ROOT / "hooks"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
