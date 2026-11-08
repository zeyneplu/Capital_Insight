FROM python:3.12-slim
WORKDIR /service
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Public AWS RDS CA bundle, so DATABASE_SSLMODE=verify-full works inside the container
# (DATABASE_SSLROOTCERT=certs/global-bundle.pem resolves to /service/certs).
RUN mkdir certs && python -c "import urllib.request; urllib.request.urlretrieve('https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem', 'certs/global-bundle.pem')"
COPY app ./app
RUN useradd --create-home --uid 1000 capital && mkdir /service/data && chown capital:capital /service/data
USER capital
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
