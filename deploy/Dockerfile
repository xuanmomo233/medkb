FROM node:22-alpine AS web
WORKDIR /w
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /srv
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir '.[sync]' \
    && useradd --system --uid 10001 --home /nonexistent --shell /usr/sbin/nologin medkb
COPY backend/scripts ./scripts
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY --from=web /w/dist /app/web
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
USER medkb
# 只信任私网/回环代理的 X-Forwarded-For：公网 IP 直连不解析 XFF，防限速 IP 维伪造
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"]
