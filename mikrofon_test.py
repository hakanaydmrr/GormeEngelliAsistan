import speech_recognition as sr

def listele_mikrofonlari():
    print("--- SİSTEMDEKİ MİKROFONLAR ---")
    # Tüm mikrofon isimlerini al
    mikrofonlar = sr.Microphone.list_microphone_names()
    
    for i, isim in enumerate(mikrofonlar):
        print(f"İndeks {i}: {isim}")
    print("------------------------------")
    print("Hangi mikrofonu kullanmak istiyorsan yanındaki numarayı not et.")

if __name__ == "__main__":
    listele_mikrofonlari()