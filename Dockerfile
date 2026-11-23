FROM python:3.11-slim

# Hugging Face Spaces runs containers as a non-root user (uid 1000)
RUN useradd -m -u 1000 user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
USER user
# CPU-only PyTorch keeps the image much smaller than the default build
RUN pip install --no-cache-dir --user torch torchvision --index-url https://download.pytorch.org/whl/cpu  && pip install --no-cache-dir --user -r requirements.txt easyocr

# Download the OCR model at build time so the first upload is not slow
RUN python -c "import easyocr; easyocr.Reader(['en'], gpu=False)"

COPY --chown=user . .

ENV DATA_DIR=/home/user/app/data WARM_OCR=1 PORT=7860
EXPOSE 7860
# One worker: the OCR model is large and is loaded once. Threads handle concurrent requests.
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-7860} --workers 1 --threads 4 --timeout 900"]
