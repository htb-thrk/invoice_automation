FROM python:3.11-slim

WORKDIR /app

COPY modules/ /app/modules/

COPY functions/kintone-pusher/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY functions/kintone-pusher/main.py /app/main.py

ENV PORT=8080
CMD exec functions-framework --target=on_json_finalized --signature-type=cloudevent