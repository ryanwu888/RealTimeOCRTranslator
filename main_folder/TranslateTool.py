from transformers import MarianMTModel, MarianTokenizer
import torch
import time
print(torch.cuda.is_available())

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(device)

# Model: Japanese to English
model_name = "Helsinki-NLP/opus-mt-ja-en"
model = MarianMTModel.from_pretrained(model_name).to(device)
tokenizer = MarianTokenizer.from_pretrained(model_name)

def translate_japanese_to_english(japanese_text):
    # Tokenize input text
    inputs = tokenizer(japanese_text, return_tensors="pt", padding=True, truncation=True).to(device)
    
    # Generate translation
    translated = model.generate(**inputs, max_length=512)
    
    # Decode result
    english_text = tokenizer.decode(translated[0], skip_special_tokens=True)
    return english_text

start_time = time.time()
# Example
jp = "今日はとても暑いですね。"
en = translate_japanese_to_english(jp)
print("[Timing] Translation took {:.4f} seconds".format(time.time() - start_time))
print(f"JP: {jp}\nEN: {en}")
