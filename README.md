# 🎮 Switch Select v3

Aplicación web para que tus clientes elijan los juegos a instalar en su Nintendo Switch.
Catálogo gestionado desde el panel admin, accesible 24/7 desde cualquier dispositivo.

---

## 🚀 OPCIÓN 1 — Railway (nube, gratis, recomendado)

La app vive en internet aunque tu PC esté apagado.

### Pasos:

1. **Sube el código a GitHub**
   ```
   git init
   git add .
   git commit -m "Switch Select v3"
   git remote add origin https://github.com/TU_USUARIO/switch-select.git
   git push -u origin main
   ```

2. **Crea cuenta en Railway**
   - Ve a https://railway.app
   - "New Project" → "Deploy from GitHub repo"
   - Selecciona tu repositorio

3. **Añade variable de entorno**
   - En Railway → tu proyecto → Variables
   - Añade: `SECRET_KEY` = (una cadena aleatoria larga, ej: `xK9!mP2#qR7$vL4@nJ8`)

4. **Railway asigna una URL** tipo `https://switch-select-xxx.railway.app`
   - Esa es la URL que das a los clientes

5. **Primer acceso admin**
   - Usuario: `admin` / Contraseña: `admin123`
   - ⚠️ Cámbiala inmediatamente

---

## 🐳 OPCIÓN 2 — Docker (tu propio servidor o VPS)

Funciona en Windows, Mac, Linux o cualquier VPS.

### Requisitos:
- Docker Desktop instalado (https://docs.docker.com/get-docker/)

### Arrancar:
```bash
docker-compose up -d
```
La app queda en http://localhost:5000 (o http://IP_DEL_SERVIDOR:5000)

### Parar:
```bash
docker-compose down
```

### Ver logs:
```bash
docker-compose logs -f
```

La base de datos se guarda en `./data/switch_selector.db` — haz copias de seguridad de esta carpeta.

---

## 💻 OPCIÓN 3 — Python directo (Windows/Mac/Linux)

```bash
pip install flask werkzeug
python app.py
```
Accede en http://localhost:5000

---

## 📋 FLUJO DE USO

1. **Tú (admin)** entras en `/admin` y añades los juegos al catálogo
   - Uno a uno, o importando varios a la vez (un juego por línea)
   - Las carátulas se buscan automáticamente en SteamGridDB
   
2. **Creas un usuario** para cada cliente con su nombre y tamaño de microSD

3. **El cliente entra** con su usuario y elige los juegos que quiere
   - Ve la barra de microSD en tiempo real
   - Puede añadir una nota al confirmar el pedido

4. **Tú ves el pedido** en el panel admin
   - Cambias el estado: Pendiente → En proceso → Completado
   - Puedes añadir una nota de respuesta que el cliente verá

5. **Instalas los juegos** manualmente en la Switch y marcas como completado

---

## 🔑 API KEY STEAMGRIDDB

La app incluye una key por defecto que funciona. Si quieres usar la tuya propia:
1. Regístrate en https://www.steamgriddb.com
2. Perfil → Preferencias → API → Generar key
3. Admin → Configuración → pega la key

---

## 🔒 SEGURIDAD

- Cambia `SECRET_KEY` en docker-compose.yml por algo aleatorio
- Cambia la contraseña de admin nada más instalar
- Railway usa HTTPS automáticamente ✅
- Si usas Docker en local, considera Nginx + Let's Encrypt para HTTPS

---

## 📁 ESTRUCTURA

```
switchapp/
├── app.py                    # Aplicación principal
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── railway.toml              # Config para Railway
├── .gitignore
├── data/                     # Base de datos (se crea automáticamente)
│   └── switch_selector.db
└── templates/
    ├── login.html
    ├── catalog.html           # Vista cliente
    ├── admin_dashboard.html   # Panel principal
    ├── admin_user.html        # Detalle cliente + gestión pedidos
    ├── admin_games.html       # Gestión catálogo
    └── admin_preview.html     # Vista previa biblioteca
```
