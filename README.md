# SAP PM BERT Model — SAP AI Core Deployment

Türkçe bakım metinlerinden ekipman tipi ve arıza kodu tahmin eden Flask servisi. **Sadece SAP AI Core** üzerinde serving olarak çalışacak şekilde yapılandırılmıştır.

## Proje yapısı

| Dosya | Açıklama |
|-------|----------|
| `app.py` | Flask API (`/v2/predict`, health endpoint'leri) |
| `serving.yaml` | SAP AI Core ServingTemplate tanımı |
| `Dockerfile` | Container imajı (BERT + model ağırlıkları) |
| `.github/workflows/build.yml` | Docker Hub'a imaj push |

## Önemli: Endpoint kuralı

SAP AI Core, custom container endpoint'lerinin **`/v1/...` veya `/v2/...`** ile başlamasını zorunlu kılar. `/predict` gibi versiyonsuz path'ler inference isteğinde **404** döner.

Bu projede tahmin endpoint'i: **`POST /v2/predict`**

---

## 1. Docker imajını yeniden oluştur

Değişikliklerden sonra imajı yeniden build edip push et:

1. GitHub → **Actions** → **SAP AI Core Docker İmajını Hazırla** → **Run workflow**
2. Veya lokal:

```bash
docker build -t ahmettahaakturk25/sap-pm-model:latest .
docker push ahmettahaakturk25/sap-pm-model:latest
```

## 2. SAP AI Core'da yeniden deploy

1. Git repo AI Core'a sync edilmiş olmalı (`serving.yaml` güncel)
2. **Configuration** oluştur (executable: `sap-pm-infer`, scenario: `sap-pm-scenario`)
3. **Deployment** oluştur ve **RUNNING** olmasını bekle
4. Deployment ID'yi not al (ör. `d4a1b2c3d5e6f7g8`)

`resourcePlan` değeri tenant'ınıza göre `starter` veya `basic` olabilir. Hata alırsanız AI Launchpad'deki mevcut plan adını `serving.yaml` içinde güncelleyin.

---

## 3. Postman ile token alma ve istek atma

BTP e-posta/şifre ile API çağrısı yapılmaz. **AI Core service key** (client credentials) gerekir.

### Service key'i al

1. BTP Cockpit → Subaccount → **Instances and Subscriptions**
2. **aicore** (veya **sap-ai-core**) instance → **Create Service Key**
3. JSON'dan şu alanları kopyala:

```json
{
  "url": "https://<subdomain>.authentication.<region>.hana.ondemand.com",
  "clientid": "...",
  "clientsecret": "...",
  "serviceurls": {
    "AI_API_URL": "https://api.ai.<region>.aws.ml.hana.ondemand.com"
  }
}
```

### Postman environment değişkenleri

| Değişken | Değer |
|----------|-------|
| `tokenURL` | `{url}/oauth/token` — **/oauth/token eklemeyi unutma** |
| `clientId` | `clientid` |
| `clientSecret` | `clientsecret` |
| `AI_API_URL` | `serviceurls.AI_API_URL` |
| `deploymentId` | Deployment oluşturduktan sonra aldığın ID |
| `resourceGroup` | Genelde `default` |

---

### Adım A — OAuth token al

| Alan | Değer |
|------|-------|
| Method | `POST` |
| URL | `{{tokenURL}}` |
| Headers | `Content-Type: application/x-www-form-urlencoded` |
| Body (x-www-form-urlencoded) | `grant_type=client_credentials` |
| | `client_id={{clientId}}` |
| | `client_secret={{clientSecret}}` |

**Tests** sekmesine ekle (token otomatik kaydedilsin):

```javascript
var json = pm.response.json();
pm.environment.set("access_token", json.access_token);
```

Başarılı yanıt:

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### Adım B — Deployment listesini kontrol et (opsiyonel)

| Alan | Değer |
|------|-------|
| Method | `GET` |
| URL | `{{AI_API_URL}}/v2/lm/deployments` |
| Headers | `Authorization: Bearer {{access_token}}` |
| | `AI-Resource-Group: {{resourceGroup}}` |

Yanıtta deployment `id` ve `status: RUNNING` olduğunu doğrula.

---

### Adım C — Tahmin isteği (asıl servis)

| Alan | Değer |
|------|-------|
| Method | `POST` |
| URL | `{{AI_API_URL}}/v2/inference/deployments/{{deploymentId}}/v2/predict` |
| Headers | `Authorization: Bearer {{access_token}}` |
| | `AI-Resource-Group: {{resourceGroup}}` |
| | `Content-Type: application/json` |
| Body (raw JSON) | Aşağıdaki örnek |

```json
{
  "text": "Çalışırken alt taraftan sürekli tık tık vuruntu sesi geliyor"
}
```

**Beklenen yanıt (200):**

```json
{
  "Ariza_Kodu": "Aşırı Titreşim (%87.3 Emin)",
  "Ekipman_Tipi": "Santrifüj Pompa (%92.1 Emin)"
}
```

---

## Sık karşılaşılan hatalar

| Hata | Olası neden | Çözüm |
|------|-------------|-------|
| 401 Unauthorized | Yanlış token URL veya süresi dolmuş token | `url` + `/oauth/token` kullan, yeni token al |
| 404 Not Found | Yanlış deployment ID veya `/predict` kullanımı | URL'de `/v2/predict` olduğundan emin ol |
| 403 RBAC | Yanlış resource group | `AI-Resource-Group: default` (veya doğru grup) |
| Deployment PENDING/FAILED | Eski imaj veya resource plan | Yeni imaj push et, `serving.yaml` resourcePlan kontrol et |

---

## Lokal test

```bash
pip install -r requirements.txt
gdown "https://drive.google.com/uc?id=10vVlPhSEeExRuBnvNnOUGjp9vtTEUQFc" -O multi_task_bert_model.pth
python app.py
```

```bash
curl -X POST http://localhost:9000/v2/predict -H "Content-Type: application/json" -d "{\"text\": \"Motor aşırı ısınıyor\"}"
```
