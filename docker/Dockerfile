FROM python:3.12-slim

RUN pip install uv

WORKDIR /app

COPY . .

RUN uv sync --no-dev

RUN uv run python scripts/download_fonts.py

RUN mkdir -p cache/menu cache/og logs

CMD ["uv", "run", "python", "app.py"]
