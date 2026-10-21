FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY brain.py .
RUN useradd -m agent
USER agent