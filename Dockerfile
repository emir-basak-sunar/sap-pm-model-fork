# Hafif bir Python sürümü kullanıyoruz
FROM python:3.10-slim

# Çalışma klasörümüzü belirliyoruz
WORKDIR /app

# Gereksinimleri kopyala ve kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kodları kopyala
COPY . .

# İnternete açılacak kapı (SAP AI Core 9000 portunu sever)
EXPOSE 9000

# Sunucuyu başlat
CMD ["gunicorn", "app:app", "--timeout", "120", "-b", "0.0.0.0:9000"]
