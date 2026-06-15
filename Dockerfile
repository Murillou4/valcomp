FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN python -m pip install --upgrade pip

COPY pyproject.toml README.md ./
COPY ares_console ./ares_console
COPY ares_backend ./ares_backend
COPY valcomp_companion ./valcomp_companion

RUN python -m pip install .

EXPOSE 8000

CMD ["uvicorn", "ares_backend.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
