# Imagem base com Playwright + Chromium pré-instalados
# mcr.microsoft.com/playwright/python é a imagem oficial que já resolve o problema dos 300MB
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

# Dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código fonte
COPY . .

# Instala o browser Chromium (já vem na imagem, mas garante que está registrado)
RUN playwright install chromium --with-deps

# Porta padrão Railway
ENV PORT=8000

EXPOSE 8000

# Inicia o servidor FastAPI
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
