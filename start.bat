@echo off
cd /d "%~dp0"
call C:\Users\dhasv\anaconda3\Scripts\activate.bat
streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
