
# 🚀 How to Run the Application

This guide explains how to start the certificate validation server after you have closed your terminal or restarted your computer.

## 1. Start Support Services (Database)

First, make sure the database and Redis containers are running.

```powershell
docker compose up -d postgres redis
```

> **Note:** If they are already running, this command will just verify they are up.

## 2. Activate Virtual Environment

Activate the Python virtual environment where all dependencies are installed.

```powershell
.\venv\Scripts\activate
```

## 3. Run the Server

Start the FastAPI application with live reloading enabled.

```powershell
uvicorn app.main:app --reload
```

## Accessing the App

- **API Root**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs

## Stopping the Application

1. Press `Ctrl+C` in the terminal where the server is running to stop the Python application.
2. To stop the background database services (optional, you can leave them running):
   ```powershell
   docker compose stop
   ```
