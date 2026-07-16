# 📰 NewsPilot AI — Autonomous News Aggregation & Publishing Agent

## 🚀 Overview
This project is an **AI-powered autonomous news agent** that **automatically** fetches, summarizes, and publishes news articles on various topics. It ensures **relevance and reliability** by fetching multiple sources, verifying content, and generating **fact-checked summaries**.
![image](https://github.com/user-attachments/assets/07142275-33e9-4698-a167-2d59badd3fa1)

### **Core Features**
✅ **Fetches news** from multiple sources based on a location & topic.  
✅ **Filters duplicates & redundant articles**.  
✅ **Summarizes news** using NLP models.  
✅ **Classifies articles** into relevant categories.  
✅ **Optimizes content for SEO**.  
✅ **Publishes news automatically** on a web app.  
✅ **Generates AI-powered images** to enhance news content.  

---

## 🏗 Tech Stack
- **Frontend:** React.js + Vite + TailwindCSS v4
- **Backend:** Flask (Python)
- **LLM:** Groq API (llama-3.3-70b-versatile)
- **Web Scraping:** SerpAPI, BeautifulSoup
- **Semantic Deduplication:** BERT embeddings (bert-base-uncased) + cosine similarity
- **Zero-shot Classification:** facebook/bart-large-mnli
- **Image Generation:** Pollinations.AI + ImgBB CDN

---

## 🛠 Installation and Setup

### **1️⃣ Clone the Repository**
```bash
git clone https://github.com/divyansh44/newspilot-ai.git

```

---

## 🖥 Backend Setup (Flask API)
### **2️⃣ Creating a Virtual Environment**
Using **Conda** :
```bash
conda create --name news_env python=3.8 -y
conda activate news_env
```

Using **venv**(Recommended):
```bash
python -m venv news_env
source news_env/bin/activate  # macOS/Linux
news_env\Scripts\activate     # Windows
```

### **3️⃣ Installing Dependencies**
```bash
cd backend
pip install -r requirements.txt
```

### **4️⃣ Configuring API Keys**
Update the **`configs.yaml`** file with:
```yaml
location: "Delhi"
topic: "Technology News"

```
Set up API keys inside `config.py`:
```python
gemini_api_key = "your-gemini-api-key"
serp_api_key = "your-serp-api-key"
imgBB_api_key = "your-imgBB-api-key"


```

### **5️⃣ Running the Flask Backend**
```bash
cd backend
python3 server.py
```
The backend will start at `http://127.0.0.1:5000/`.

---

## 🌐 Frontend Setup (React)
### **6️⃣ Installing Dependencies**
```bash
cd frontend
npm install

```

### **7️⃣ Running the React Frontend**
```bash
npm run dev
```
The frontend will be available at `http://localhost:5173/`.

---




---
## 🎯 Future Improvements
✅ **Advanced NLP**: Improve summarization with better LLMs  
✅ **User Metrics**: Track views, shares, and engagement  
✅ **Multilingual Support**: Translate news into multiple languages   
---

## 📜 License
This project is open-source and available under the **MIT License**.

