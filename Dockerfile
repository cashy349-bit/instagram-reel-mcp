FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py SKILL.md ./

# Mount a cookies file at runtime and point this at it if Instagram
# starts requiring a logged-in session:
#   docker run -v /host/cookies.txt:/app/cookies.txt \
#     -e IG_REEL_COOKIES=/app/cookies.txt instagram-reel-mcp
ENV IG_REEL_COOKIES=""

CMD ["python", "server.py"]
