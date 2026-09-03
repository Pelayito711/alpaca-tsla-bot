# Bot de Trading Auto-Correctivo para Tesla (TSLA)

Bot autónomo de trading cuantitativo para operar **Tesla (`TSLA`)** en el mercado de **Nueva York (09:30 - 16:00 EST)** utilizando la estrategia institucional **Ruptura Alcista (ORB 15m) + Fair Value Gap (FVG)**.

---

## 📊 Resultados de Backtesting (60 Días, Velas de 5 Minutos)

| Activo | Estrategia | R-Factor | Win Rate | Retorno 60d | Max Drawdown | Profit Factor |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Tesla (`TSLA`)** | **ORB + FVG** | **3.00** | **39.1%** | **+27.33%** | **11.42%** | **1.93** |
| **Tesla (`TSLA`)** | **ORB + FVG** | **2.50** | **39.1%** | **+16.91%** | **11.42%** | **1.61** |
| **Tesla (`TSLA`)** | ORB + FVG | 2.00 | 39.1% | +7.27% | 11.42% | 1.29 |

> [!NOTE]
> Gracias a la alta volatilidad e impulso de Tesla (`TSLA`), las rupturas alcistas con FVG generan recorridos muy amplios. La relación riesgo/beneficio óptima es **R = 2.50 a 3.00**, alcanzando un retorno neto superior al **+16.9% / +27.3%** con un Drawdown controlado de **11.42%**.

---

## ⚙️ Características

1. **Órdenes Bracket OCO en Servidor:** Al detectar una entrada, envía una orden límite de compra con **Stop Loss** y **Take Profit** adjuntos en Alpaca.
2. **Control Anti-Duplicados:** No satura el libro si ya existe una orden pendiente esperando ejecución.
3. **Cierre Forzoso Intradía (15:55 EST):** Cancela órdenes y liquida posiciones antes de las 16:00 EST para evitar riesgo de gap nocturno.
4. **Auto-Optimizador Semanal:** Cada domingo calibra el R-Factor sobre los últimos 30 días.

---

## 🚀 Configuración en GitHub Actions

Agrega los siguientes secretos en tu repositorio de GitHub (`Settings` -> `Secrets and variables` -> `Actions`):

* `ALPACA_API_KEY`: Tu API Key ID de Alpaca (`PK...`).
* `ALPACA_SECRET_KEY`: Tu Secret Key de Alpaca.
* `ALPACA_BASE_URL`: `https://paper-api.alpaca.markets`
