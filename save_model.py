from transformers import pipeline
pipe = pipeline("zero-shot-classification")
pipe.save_pretrained("./model")