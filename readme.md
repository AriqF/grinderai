# GrinderAI - Daily Level Up AI Assistant

GrinderAI adalah chatbot berbasis Telegram yang dirancang untuk membantu pengguna mencapai tujuan jangka panjang mereka dengan memandu pencapaian target harian yang menggunakan gamifikasi. GrinderAI memecah tujuan besar yang dibagikan oleh pengguna menjadi langkah-langkah harian yang lebih mudah dicapai.

Selain berperan sebagai asisten produktivitas, bot ini juga dapat menjadi teman harian, di mana pengguna bisa berbagi cerita tentang kesehariannya. GrinderAI kemudian memberikan respons berupa arahan atau validasi untuk membantu meningkatkan kualitas hari pengguna. Pengguna juga dapat meninjau kembali perjalanan hariannya melalui analisis sentimen dan catatan cerita yang telah mereka bagikan sebelumnya, yang berguna sebagai sarana refleksi dan evaluasi diri.

---

## 🎯 MVP Goals (20 June – 27 June)
1. User can set their long-term goals  
2. AI can break down user's long-term goals into structured daily goals  
3. User can validate they’ve done daily goals  
4. AI can remind the user if they haven’t done the daily goals  
5. Gamification: EXP for doing the daily goals  

---

## 🔁 Flow:
1. User start bot agar bot dapat di-allow untuk interaksi lebih dulu kepada user  
2. Bot menanyakan nama user yang bisa dipanggil pada user  
3. Bot menanyakan goals jangka panjang yang ingin diraih oleh user. Bot menunjukkan komponen-komponen template (contoh:  
   - Fisik: weight loss, gain, dll  
   - Otak: learn new skill)  
   - Others
4. User memberikan input  
5. Bot membuat goals harian yang bisa dilakukan oleh user untuk meraih goal jangka panjang (contoh: push up 10x, read a book 15 minutes)  
6. User memberikan feedback goals harian  
7. Bot menyimpan goals harian yang telah disetujui  
8. Bot memberikan arahan user untuk menuliskan atau bercerita mengenai mood hari ini  

---

## 🚀 Tech Stack:
- **Platform**: Telegram Bot API  
- **Backend**: Python FastAPI
- **AI/NLP**: OpenAI API 
- **Database**: MongoDB  
- **Other Tools**: Langchain, CronJob

---

## License
MIT License


## Running FastAPI
1. Windows: 
   - source .venv/Scripts/activate (bash) or .venv/Scripts/Activate.ps1  (powershell)
   - uvicorn app.main:main --reload
2. MacOS
   - .venv/Scripts/activate 
   - uvicorn app.main:main --reload
