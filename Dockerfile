FROM python:3.13-slim AS builder
WORKDIR /service
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev && rm -rf /var/lib/apt/lists/*
COPY src/ src/
COPY include/ include/
COPY scripts/build_native.py scripts/build_native.py
RUN python scripts/build_native.py
COPY pyproject.toml ./
COPY app/ app/
RUN pip wheel --no-cache-dir --wheel-dir /wheels .

FROM builder AS test
COPY tests/ tests/
COPY scripts/ scripts/
RUN pip install --no-cache-dir '.[test]'
RUN python -m pytest -q && python scripts/check_native_memory.py --sanitize

FROM python:3.13-slim
WORKDIR /service
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels vcard-parser-service && rm -rf /wheels \
    && useradd --create-home service && mkdir /service/data && chown service:service /service/data
COPY --from=builder /service/build/libvcparser.so /service/build/libvcparser.so
ENV VCARD_LIBRARY_PATH=/service/build/libvcparser.so DATABASE_URL=sqlite:////service/data/cards.db
USER service
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
