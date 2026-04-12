import random
import time

def generate_metrics(mode):
    if mode == "normal":
        cpu = random.randint(20, 60)
        memory = random.randint(30, 70)
    else:  
        cpu = random.randint(80, 100)
        memory = random.randint(75, 95)
    
    return cpu, memory


while True:
    mode = random.choice(["normal", "attack"])
    
    cpu, memory = generate_metrics(mode)
    
    print(f"[INFO] Mode: {mode}")
    print(f"[INFO] CPU Usage: {cpu}%")
    print(f"[INFO] Memory Usage: {memory}%")
    
    if cpu > 80:
        print("[ALERT] High CPU usage detected!")
    
    print("-" * 40)
    
    time.sleep(2)

    if memory > 85:
        print("[ALERT] High Memory usage detected!")