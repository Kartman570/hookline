FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home app
COPY hookline hookline
RUN mkdir /data && chown app:app /data
USER app
ENV HOOKLINE_DATABASE=/data/hookline.sqlite3
CMD ["uvicorn", "hookline.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
