# MarquiBot Web — Mármoles Marquitec

## Correr localmente (red WiFi de oficina)

```
pip install flask werkzeug
python app.py
```

Abrir en cualquier PC de la red: http://IP_DEL_PC:5000

---

## Subir a Railway (internet, gratis)

1. Ir a https://railway.app y crear cuenta con GitHub
2. Crear nuevo proyecto → "Deploy from GitHub repo"
3. Subir esta carpeta a GitHub primero:
   - Crear repo en https://github.com/new
   - git init
   - git add .
   - git commit -m "MarquiBot"
   - git remote add origin https://github.com/TU_USUARIO/marquibot.git
   - git push -u origin main
4. En Railway → conectar el repo → Deploy
5. Listo. Te da una URL pública tipo: https://marquibot-production.up.railway.app

---

## Subir a Render (alternativa gratuita)

1. Ir a https://render.com
2. New → Web Service → Connect GitHub repo
3. Build Command: pip install -r requirements.txt
4. Start Command: gunicorn app:app
5. Deploy → URL pública lista en 2 minutos

---

## Archivos importantes
- app.py — backend Flask
- marquibot_data.db — base de datos (se crea automático)
- static/uploads/ — PDFs y archivos subidos
- templates/ — páginas HTML
