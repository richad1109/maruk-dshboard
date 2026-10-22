# Kantor Rakus ? Bot Sakti monitoring

Streamlit dashboard for eight real futures wallets: three Bitget, two MEXC and three BingX. The app only reads data. It never places, cancels, closes or transfers.

## Run locally

Install requirements, then `streamlit run streamlit_app.py`. Configure accounts using Streamlit Secrets `accounts_json`, nested `accounts`, environment `MARUK_ACCOUNTS_JSON`, or an ignored local accounts_config.json. Never commit API credentials.

## Streamlit Community Cloud

Use repository richad1109/maruk-dshboard, branch main, entrypoint streamlit_app.py. Before switching from the legacy app, move the existing credentials to app Settings ? Secrets as accounts_json (the same JSON account structure). API config and old financial state files were removed from the new source tree. Existing Cloud secrets are preserved by a code deployment.

## Termux journal

Exchange balances and positions are direct API reads; Bot Sakti alerts, net closed-trade PnL and health sizing require the Termux journal. Run sakti_monitor.py on the phone to export sanitized sakti_monitor.json to Downloads; upload that file on the Bot Sakti tab. It is a dated snapshot, not a claim that the phone process is currently alive. For server file sync set SAKTI_STATE_PATH. API keys are never included in telemetry.

## Interface

Animated interactive CSS3D office with three desks, orbit, pause and reset. Account filters, market chart, exchange allocation, manual position badges, health budget and target monitoring. Unknown values remain unknown; there is no demo fallback. Manual assets: ETH/BTC/TIA/ONDO/BR on BingX account1 and XRP on all Bitget accounts.

## Checks

`python -m unittest discover -s tests -v`. Tests mock read APIs; production always uses real-account configuration. Private test orders are never submitted. Local QA also verified all eight real account read connections.
