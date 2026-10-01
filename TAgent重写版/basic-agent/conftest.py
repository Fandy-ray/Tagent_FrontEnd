"""全工程测试共用的环境约定（根目录的 test_*.py 与 tests/ 都会先加载这里）。"""

import os

# 单测不往真实的应用数据目录里写学习记录，也不起备份线程。
# 要测学习记录库的用例自己建临时库并注入（见 tests/test_learning_store.py）。
os.environ["LEARNING_STORE"] = "0"
