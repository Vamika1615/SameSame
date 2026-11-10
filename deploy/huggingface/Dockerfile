# Remix on Hugging Face Spaces (Docker SDK). The Space holds only this file and README.md:
# it clones the public GitHub repo, builds the frontend, installs the backend, runs the data
# pipeline once at build time (synthetic, deterministic from the seed), then serves everything
# from one FastAPI process on port 7860.
ARG REPO=https://github.com/Vamika1615/SameSame.git
ARG REF=main

# ---------- 1. fetch the code and build the frontend ----------
FROM node:20-slim AS web
ARG REPO
ARG REF
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
# Changes whenever main moves on GitHub, so a rebuild always picks up the latest commit.
ADD https://api.github.com/repos/Vamika1615/SameSame/git/refs/heads/main /tmp/version.json
RUN git clone --depth 1 --branch "$REF" "$REPO" /src
WORKDIR /src/frontend
RUN npm ci --no-audit --no-fund && npm run build

# ---------- 2. backend + data ----------
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
WORKDIR /app
COPY --from=web /src/backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r /app/backend/requirements.txt
COPY --from=web --chown=user /src/backend /app/backend
COPY --from=web --chown=user /src/data /app/data
COPY --from=web --chown=user /src/frontend/dist /app/frontend/dist
COPY --from=web --chown=user /src/*.md /app/

USER user
ENV HOME=/home/user PYTHONUNBUFFERED=1 HF_HUB_DISABLE_TELEMETRY=1
WORKDIR /app/backend
# Builds data/build (feeds, matcher, Promise model, Remix, metrics); downloads the MiniLM model into data/models.
RUN python -m samesame.pipeline

EXPOSE 7860
CMD ["python", "-m", "uvicorn", "samesame.api.app:app", "--host", "0.0.0.0", "--port", "7860"]
