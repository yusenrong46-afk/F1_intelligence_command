# Bylaw rule verification: the bylaw-verify CLI and the command-center demo.
# No API key, no paid call. Build:  docker build -t bylaw-rule-verification .
#   docker run --rm bylaw-rule-verification bylaw-verify --help
#   docker run --rm -p 8631:8631 bylaw-rule-verification        # demo on :8631
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt pyproject.toml README.md ./
# Behind a TLS-intercepting proxy, pass its CA bundle as a build secret:
#   docker build --secret id=ca,src=/path/to/ca-bundle.crt .
# It is used for this pip step only and never stored in the image.
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export PIP_CERT=/run/secrets/ca; fi; \
    pip install -r requirements.txt "setuptools>=68" wheel

COPY . .
# Editable install so bylaw-verify finds schemas/ next to src/.
RUN pip install --no-build-isolation -e . \
    && python scripts/build_chat_context_db.py --outputs-root outputs/m7_runs >/dev/null \
    && useradd --create-home --uid 10001 app && chown -R app /app
USER app

EXPOSE 8631
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8631/_stcore/health', timeout=4).read().strip()==b'ok' else 1)"
CMD ["python", "-m", "streamlit", "run", "streamlit_app.py", "--server.port", "8631", \
     "--server.address", "0.0.0.0", "--server.headless", "true", "--browser.gatherUsageStats", "false"]
