import google.generativeai as genai

# Senin API Anahtarın
API_KEY = "AIzaSyCs_qBz7jqUkLOikSHncEdAgChjxNLb0E4"

genai.configure(api_key=API_KEY)

print("Erişebildiğin Modeller Listeleniyor...\n")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"Model Adı: {m.name}")
except Exception as e:
    print(f"Hata oluştu: {e}")