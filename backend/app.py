from fastapi import FastAPI
import random

app = FastAPI()

def generate_metrics():
    mode = random.choice(["normal", "attack"])
    
    if mode == "normal":
        cpu = random.randint(20, 60)
        memory = random.randint(30, 70)
    else:
        cpu = random.randint(80, 100)
        memory = random.randint(75, 95)

    return {
        "mode": mode,
        "cpu": cpu,
        "memory": memory
    }

@app.get("/")
def home():
    return {"message": "CloudScope API is running 🚀"}

@app.get("/metrics")
def get_metrics():
    data = generate_metrics()

    alert = None
    if data["cpu"] > 80:
        alert = "High CPU usage detected!"
    elif data["memory"] > 85:
        alert = "High Memory usage detected!"

    return {
        "data": data,
        "alert": alert
    }
