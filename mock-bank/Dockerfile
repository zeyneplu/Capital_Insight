FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY pyproject.toml ./
COPY mockbank ./mockbank
COPY data/customers.json ./data/customers.json
RUN pip install --no-cache-dir .

# Run as a non-root user.
RUN useradd --create-home bank && chown -R bank /app
USER bank

EXPOSE 8000
CMD ["uvicorn", "mockbank.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
