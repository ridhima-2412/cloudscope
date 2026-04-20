# CloudScope 🚀

**Real-Time Cloud Infrastructure Monitoring Dashboard**

CloudScope is a full-stack cloud monitoring dashboard designed to track live infrastructure health, system performance, alerts, anomalies, and optimization insights. It connects frontend + backend services and can be integrated with AWS EC2 instances for real-time metrics collection.

---

# 📌 Features

## 📊 Real-Time Monitoring

* CPU Usage
* Memory / RAM Usage
* Disk Usage
* Network In / Out
* Latency Metrics
* Timestamps
* Auto Refresh / Polling

## 🚨 Smart Alerts

* High CPU Alerts
* Memory Threshold Alerts
* Disk Usage Warnings
* Healthy / Warning / Critical Status Indicators

## 🤖 Anomaly Detection

* Anomaly Score
* Suspicious Usage Pattern Detection
* Resource Spike Identification

## 📈 Visualization

* Metric Cards
* Charts / Graphs
* Historical Trends
* Live Dashboard Updates

## ☁️ AWS Integration

* Connect to AWS EC2 Instance
* Fetch Real System Metrics
* SSH-based Monitoring
* Secure `.env` Configuration

## 🐳 Docker Support

* Dockerized Frontend + Backend
* Easy Multi-Service Startup
* Portable Deployment

---

# 🏗️ Tech Stack

## Frontend

* Streamlit / React *(depending on your implementation)*

## Backend

* Python (FastAPI / Flask)

## Cloud

* AWS EC2

## DevOps

* Docker
* Docker Compose

---

# 📂 Project Structure

```text id="g92a1p"
CloudScope/
│── frontend/
│── backend/
│── docker-compose.yml
│── Dockerfile
│── .env
│── requirements.txt
│── README.md
```

---

# ⚙️ Setup Instructions

## 1️⃣ Clone the Repository

```bash id="qmb7v7"
git clone <your-repo-url>
cd CloudScope
```

---

# 🔐 Environment Variables

Create a `.env` file in the root folder:

```env id="l31k7h"
AWS_HOST=54.82.239.35
AWS_DNS=ec2-54-82-239-35.compute-1.amazonaws.com
AWS_USER=ec2-user
AWS_PORT=22
AWS_REGION=us-east-1
AWS_KEY_PATH=./keys/your-key.pem

POLL_INTERVAL=5

CPU_ALERT_THRESHOLD=80
MEMORY_ALERT_THRESHOLD=80
DISK_ALERT_THRESHOLD=85

APP_ENV=development
```

> Replace `AWS_KEY_PATH` with your actual `.pem` file path.

---

# ▶️ Run Locally

## Backend

```bash id="csj0pi"
cd backend
pip install -r requirements.txt
python app.py
```

## Frontend

```bash id="0cdlga"
cd frontend
streamlit run app.py
```

*(If using React frontend, run `npm install && npm run dev` instead.)*

---

# 🐳 Run with Docker

```bash id="pbjjye"
docker-compose up --build
```

Then open your browser:

```text id="45azup"
Frontend: http://localhost:8501
Backend:  http://localhost:8000
```

*(Ports may vary depending on your setup.)*

---

# ☁️ AWS EC2 Integration

CloudScope connects to your EC2 instance using SSH and fetches metrics like:

* CPU
* RAM
* Disk
* Network
* Latency
* Running Status

### Test SSH Manually

```bash id="8flr68"
ssh -i your-key.pem ec2-user@54.82.239.35
```

If login works, CloudScope can connect successfully.

---

# 📡 API Endpoints (Example)

```text id="z45pkw"
GET /health
GET /metrics
GET /alerts
GET /history
```

---

# 📸 Dashboard Overview

The dashboard includes:

* Live Metric Cards
* Historical Charts
* Alert Panel
* Health Status Badges
* Last Updated Timestamp
* AWS Source Indicator

---

# 🧪 Troubleshooting

## No Data Showing

* Check backend is running
* Check frontend API URL
* Verify `.env` values
* Confirm AWS instance is running
* Test SSH manually
* Check Docker logs

## SSH Failed

* Verify `.pem` file
* Check Security Group port 22
* Confirm username is `ec2-user`

## Docker Issues

```bash id="ttkgz7"
docker-compose down
docker-compose up --build
```

---

# 🔮 Future Improvements

* Multi-instance Monitoring
* CloudWatch Integration
* Email / Slack Alerts
* Authentication
* Role-based Access
* Database Storage
* Predictive Analytics
* Cost Forecasting

---

##DEMO VIDEO LINK :[ https://1drv.ms/v/c/77a183bd730fde19/IQDJLMYUkbxCSrmhpP7bUAkqAcuwCkzvty5aC-e8vP211ao?e=Mf01vw](url)
