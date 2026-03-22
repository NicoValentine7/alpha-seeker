FROM python:3.12-slim

WORKDIR /app

# システム依存
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# uv インストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 依存インストール（キャッシュ活用のため先にコピー）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ソースコード
COPY src/ src/

# デフォルトコマンド: スコアリング実行
CMD ["uv", "run", "python", "-m", "stock_ranking.ranking", "--top", "50"]
