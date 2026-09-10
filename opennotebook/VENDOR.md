# 这份目录的来历

从 <https://gitee.com/kevin-zhengscuter/fixed_open_notebook> 原样复制（master，
2026-08-24 抓取），只改了两处，都是为了不让密钥写死在文件里：

| 文件 | 改动 |
|---|---|
| `docker-compose.yml` | `OPEN_NOTEBOOK_ENCRYPTION_KEY` 改成读 `${OPEN_NOTEBOOK_ENCRYPTION_KEY:-...}`，由 `start.bat` 往同目录 `.env` 里生成一个随机值 |
| `docker-compose.yml` | `DASHSCOPE_API_KEY` 改成读 `${DASHSCOPE_API_KEY:-}`，避免把阿里云 Key 写进 yml |

其余文件（`readme.md`、`aliyun-tts-bridge/`、`docs/`）未改动。上游更新时可直接
覆盖，然后把上面两行重新打上。

## 这里**没有** OpenNotebook 的源码

本目录只是一份 docker-compose 部署描述。真正的程序是启动时从 Docker Hub 拉的镜像：

- `lfnovo/open_notebook:v1-latest` — 页面 8502 / 接口 5055
- `surrealdb/surrealdb:v2` — 数据库，仅监听 127.0.0.1:8000

所以**第一次启动需要联网**，镜像有 GB 级，国内建议先配 Docker 镜像加速（见
`readme.md` 第三步）。

## 数据存在哪

- `notebook_data/` — 笔记本、来源、笔记
- `surreal_data/` — SurrealDB 数据文件

两个目录都在本目录下，由 Docker 首次启动时创建。**这是你所有笔记的实际存放位置**，
换机器要连同这两个目录一起搬。它们已被 `.gitignore` 排除。

## TTS / 播客

`aliyun-tts-bridge` 默认**不启动**（需要阿里云 DashScope Key，交接包里没有）。
要用的话给 `start.bat` 加 `-WithTts`，并在本目录 `.env` 里填 `DASHSCOPE_API_KEY=`。
