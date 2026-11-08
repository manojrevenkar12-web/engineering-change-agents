FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY config ./config
COPY data ./data
COPY models/registry.json ./models/registry.json
RUN pip install --no-cache-dir . && python -m eca.cli lim-train > /dev/null
EXPOSE 8000
CMD ["uvicorn", "eca.api:app", "--host", "0.0.0.0", "--port", "8000"]
