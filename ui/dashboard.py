import streamlit as st
import requests
import time

st.title("☁️ CloudScope Dashboard")

url = "http://backend:8000/metrics"

if st.button("Refresh Data"):
    for i in range(5):  # retry 5 times
        try:
            response = requests.get(url)
            data = response.json()

            cpu = data["data"]["cpu"]
            memory = data["data"]["memory"]
            alert = data["alert"]

            st.subheader("📊 Metrics")
            st.write(f"CPU Usage: {cpu}%")
            st.write(f"Memory Usage: {memory}%")

            if alert:
                st.error(f"🚨 {alert}")
            else:
                st.success("✅ System Normal")

            break

        except:
            st.warning("Retrying connection...")
            time.sleep(2)
    else:
        st.error("⚠️ API not reachable")