"""压测用后端：真实的 main.py 应用（真实知识库：教材 + 论文 + FAISS + 检索结果缓存、真实嵌入模型），只有模型换成假上游。

和 chaos_server 的区别：chaos_server 的知识库是假的（固定一段文字），测不到检索的开销；这里检索全是真的。

    .venv/bin/python -m tools.chaos.fake_upstream     # 假上游 9100
    .venv/bin/python -m tools.chaos.load_backend      # 本后端，默认 5011（LOAD_PORT 可改），不占正式的 5001
    .venv/bin/python -m tools.chaos.load_rag          # 压测

模型登记和学习记录都写进临时目录（启动时打印路径），不碰正式的配置和数据；目录不自动删，
留着可以核对学习记录有没有丢写，用完自己删。只用本地知识（不连 OpenNotebook：它的检索可能调付费的嵌入服务）。
向量索引缓存沿用正式的缓存目录，内容和正式启动建的一样，省得每次都重建。
"""
import os
import sys
import tempfile
from pathlib import Path

BA = Path(__file__).resolve().parents[2]  # basic-agent/
sys.path.insert(0, str(BA))
os.chdir(BA)

work = Path(tempfile.mkdtemp(prefix="load-"))
# 先设好再导入 main：main 里的 load_dotenv 不覆盖已有的环境变量
os.environ.update({
    "BASIC_AGENT_HOST": "127.0.0.1",
    "BASIC_AGENT_PORT": os.getenv("LOAD_PORT", "5011"),
    "MODEL_PROVIDERS_PATH": str(work / "providers.json"),
    "TAGENT_DB_PATH": str(work / "tagent.sqlite3"),
    "KNOWLEDGE_SOURCE": "local",
})

from app.repository.provider_repository import ModelProviderRegistry  # noqa: E402

ModelProviderRegistry(work / "providers.json").create_provider({
    "name": "DeepSeek（假上游）", "served_model_id": "deepseek",
    "base_url": os.getenv("CHAOS_UPSTREAM", "http://127.0.0.1:9100") + "/v1",
    "upstream_model": "fake-model", "auth_mode": "none", "api_key": "", "enabled": True,
})

import main  # noqa: E402

if __name__ == "__main__":
    print(f"load backend: port={os.environ['BASIC_AGENT_PORT']} work={work}", flush=True)
    main.main()
