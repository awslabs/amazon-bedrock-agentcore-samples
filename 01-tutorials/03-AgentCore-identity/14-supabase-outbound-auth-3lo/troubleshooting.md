# Troubleshooting

## Streamlit not loading in WSL2

**Symptom:** Browser shows "This page isn't working" or `ERR_EMPTY_RESPONSE` when opening the Streamlit app from Windows.

**Cause:** Streamlit tries to auto-open a browser on startup. In WSL2 there is no desktop environment, so this call blocks the event loop before any HTTP requests are served.

**Fix:** Add `--server.headless true` to the run command:

```bash
python oauth2_callback_server.py -r <region> &
streamlit run chatbot_app_supabase.py --server.address=0.0.0.0 --server.port=8501 --server.headless true
```

Then forward the port in VS Code (**Ports** tab → **Forward a Port** → `8501`) and open `http://localhost:8501` in your Windows browser.
