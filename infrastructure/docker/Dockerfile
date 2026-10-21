FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY siteforge ./siteforge
COPY benchmarks ./benchmarks
RUN pip install --no-cache-dir . && useradd --create-home --uid 10001 siteforge
USER siteforge
EXPOSE 8080
CMD ["uvicorn", "siteforge.api:app", "--host", "0.0.0.0", "--port", "8080"]
