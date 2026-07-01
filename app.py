from flask import Flask, request, jsonify, render_template_string
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer
import torch.nn as nn
from transformers import AutoModel
import os

app = Flask(__name__)
device = torch.device("cpu")

EKIPMAN_SINIFLARI = ["Bantlı Konveyör", "Basınç Sensörü", "Chiller Ünitesi", "Dişli Redüktör", "Elektrik Motoru", "Endüstriyel Fırın", "Eşanjör", "Güç Trafosu", "Hidrolik Pres", "Pnömatik Valf", "Radyal Fan", "Santrifüj Pompa", "Tavan Vinci", "Vidalı Kompresör"]
ARIZA_SINIFLARI = ["Aşırı Isınma", "Aşırı Titreşim", "Düşük Basınç / Debi", "Elektriksel Arıza", "Fonksiyon Kaybı (Açılmıyor/Kapanmıyor)", "Gürültülü Çalışma", "Sinyal Yok / Okuma Hatası", "Sıkışma / Kilitlenme", "Sızıntı / Kaçak"]

MODEL_NAME = "dbmdz/bert-base-turkish-cased"

class MultiTaskBERT(nn.Module):
    def __init__(self, model_name, num_ekipman, num_ariza):
        super(MultiTaskBERT, self).__init__()
        self.bert = AutoModel.from_pretrained(model_name)
        self.drop = nn.Dropout(p=0.3)
        self.out_ekipman = nn.Linear(self.bert.config.hidden_size, num_ekipman)
        self.out_ariza = nn.Linear(self.bert.config.hidden_size, num_ariza)
        
    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = self.drop(outputs.pooler_output)
        return {
            'ekipman': self.out_ekipman(pooled_output),
            'ariza': self.out_ariza(pooled_output)
        }

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = MultiTaskBERT(MODEL_NAME, len(EKIPMAN_SINIFLARI), len(ARIZA_SINIFLARI))

# Model ağırlıklarını çalışma dizininden alıyor
model_path = "multi_task_bert_model.pth"
if os.path.exists(model_path):
    model.load_state_dict(torch.load(model_path, map_location=device))
model.eval()

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>SAP Akıllı Arıza Asistanı</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background-color: #f4f7f6; }
        .container { max-width: 600px; background: white; padding: 30px; border-radius: 10px; box-shadow: 0px 4px 10px rgba(0,0,0,0.1); margin: auto; }
        h2 { color: #0070f2; }
        textarea { width: 100%; height: 100px; margin-bottom: 20px; padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 5px; }
        button { background-color: #0070f2; color: white; border: none; padding: 10px 20px; font-size: 16px; border-radius: 5px; cursor: pointer; width: 100%; }
        .result { margin-top: 20px; padding: 15px; background-color: #eef; border-left: 5px solid #0070f2; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🔧 SAP Akıllı Bakım Yönlendirme</h2>
        <textarea id="textInput" placeholder="Örn: Çalışırken alt taraftan sürekli tık tık vuruntu sesi geliyor..."></textarea>
        <button onclick="tahminEt()">Yapay Zeka ile Tahmin Et</button>
        <div id="resultBox" class="result">
            <strong>Ekipman:</strong> <span id="ekipman_res"></span><br><br>
            <strong>Arıza Kodu:</strong> <span id="ariza_res"></span>
        </div>
    </div>
    <script>
        async function tahminEt() {
            const text = document.getElementById('textInput').value;
            const response = await fetch('/v2/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            });
            const data = await response.json();
            document.getElementById('ekipman_res').innerText = data.Ekipman_Tipi;
            document.getElementById('ariza_res').innerText = data.Ariza_Kodu;
            document.getElementById('resultBox').style.display = 'block';
        }
    </script>
</body>
</html>
'''

@app.route('/', methods=['GET'])
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/health', methods=['GET'])
@app.route('/v1/health/live', methods=['GET'])
@app.route('/v1/health/ready', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/v2/predict', methods=['POST'])
def predict():
    data = request.get_json(force=True)
    text = str(data.get("text", ""))
    inputs = tokenizer(text, add_special_tokens=True, max_length=64, padding='max_length', truncation=True, return_tensors='pt')
    with torch.no_grad():
        outputs = model(inputs['input_ids'].to(device), inputs['attention_mask'].to(device))
    probs_e = F.softmax(outputs['ekipman'], dim=1)
    probs_a = F.softmax(outputs['ariza'], dim=1)
    top_p_e, top_idx_e = torch.max(probs_e, dim=1)
    top_p_a, top_idx_a = torch.max(probs_a, dim=1)
    return jsonify({
        "Ekipman_Tipi": f"{EKIPMAN_SINIFLARI[top_idx_e.item()]} (%{top_p_e.item()*100:.1f} Emin)",
        "Ariza_Kodu": f"{ARIZA_SINIFLARI[top_idx_a.item()]} (%{top_p_a.item()*100:.1f} Emin)"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 9000))
    app.run(host='0.0.0.0', port=port)
