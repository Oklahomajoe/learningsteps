ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY api/requirements.lock ./requirements.lock
RUN python -m pip install --no-cache-dir -r requirements.lock

RUN groupadd --gid 10001 api \
    && useradd --uid 10001 --gid 10001 \
       --no-create-home --shell /usr/sbin/nologin api

COPY --chown=10001:10001 api/ ./

USER 10001:10001
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
