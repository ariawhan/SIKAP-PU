# Wa-Gateway SIKAP-PU

Server Node.js pendamping SIKAP-PU untuk WhatsApp berbasis `wa-multi-session`.

## Cara jalan manual

```bat
cd Wa-Gateway
copy .env.example .env
npm install
npm start
```

Default server: `http://127.0.0.1:3001`

## Endpoint utama

- `GET /health`
- `GET /sessions/sikap-pu-main/status`
- `POST /sessions/sikap-pu-main/start`
- `POST /sessions/sikap-pu-main/logout`
- `POST /messages/send-text`

Kalau `WA_GATEWAY_API_KEY` diisi, semua request harus memakai header `x-api-key`.
