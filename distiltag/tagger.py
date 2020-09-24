import os
import re
import torch
import numpy as np
from .download import get_model_path
from transformers import DistilBertTokenizer
from transformers import DistilBertForTokenClassification

class DistilTag:
    def __init__(self, model_path=None, use_cuda=False):
        if not model_path:
            model_path = get_model_path()
        if not os.path.exists(model_path):
            raise FileNotFoundError("Cannot find model under " + model_path)
        self.device = "cuda" if use_cuda and torch.cuda.is_available() else "cpu"
        self.model = DistilBertForTokenClassification.from_pretrained(model_path)
        self.model.to(self.device)
        self.tokenizer = DistilBertTokenizer.from_pretrained(model_path)
        self.label_map = self.get_label_map(model_path)

    def get_label_map(self, model_path):
        label_path = os.path.join(model_path, "labels.txt")
        with open(label_path, "r") as f:
            labels = f.read().splitlines()   
            label_map = {i: label for i, label in enumerate(labels)}
        return label_map

    def make_sentences(self, text):        
        sentence_pat = re.compile("([！：，。？；）：])")
        parts = sentence_pat.split(text)
        try:
            sentences = [parts[i]+parts[i+1] for i in range(0, len(parts), 2) if parts[i]]
        except:
            sentences = [text]
        return sentences
    
    def make_tagged(self, text, pred):
        tagged = []
        buf = ["", ""]
        for ch, label in zip(text, pred):        
            if label.startswith("B-") and buf[0]:
                tagged.append(tuple(buf))
                buf = ["", ""]
            buf[0] += ch
            buf[1] = label[2:]
        if buf[0]:
            tagged.append(tuple(buf))
        return tagged
                        
    def tag(self, text):
        label_map = self.label_map
        sentences = self.make_sentences(text)
        batch = self.tokenizer(sentences, 
                    return_tensors="pt",                     
                    padding=True)
        
        if self.device == "cuda":
            for k, v in batch.items():
                batch[k] = v.to(self.device)

        with torch.no_grad():
            outs = self.model(**batch)[0]
            preds = np.argmax(outs.cpu().numpy(), axis=2)
        batch_size, seq_len = preds.shape
        input_ids = batch["input_ids"].cpu().numpy()
        preds_list = [[] for _ in range(batch_size)]

        for i in range(batch_size):
            for j in range(1,(seq_len-1)):        
                if input_ids[i, j] in (101, 102, 0):             
                    continue
                preds_list[i].append(label_map[preds[i][j]])
        
        tagged_list = [self.make_tagged(text, pred) 
                        for text, pred 
                        in zip(sentences, preds_list)]

        return tagged_list   

    def print_tagged_list(self, tagged_list):
        for tagged_x in tagged_list:
            print("\u3000".join(f"{x[0]}({x[1]})" for x in tagged_x))