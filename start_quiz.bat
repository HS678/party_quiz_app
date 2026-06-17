@echo off
cd /d D:\AAWorkspace\party_quiz_app

call D:\Anaconda\condabin\conda.bat activate FL1

streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true