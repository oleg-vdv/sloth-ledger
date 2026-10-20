# Judge on the synthetic statement

205 senders over July–September 2026: 200 customers and 5 people named in the owner's notes. Ollama on an RTX 5050 laptop (8 GB VRAM), temperature 0, thinking off, 12 senders per call.

| Model | Time for 205 senders | Named people right | Sent to you to check | Wrong and confident | Overall |
|---|---|---|---|---|---|
| `gemma4:12b` | 17 min 23 s | 5/5 | 9 | 0 | 95.6 % |
| `llama3.1:8b` | 2 min 50 s | 5/5 | 69 | 0 | 78.5 % |
| `gemma4:e2b-it-qat` | 1 min 42 s | 5/5 | 200 | 0 | 13.2 % |
