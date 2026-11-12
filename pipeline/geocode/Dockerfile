# Arama dizini üretimi (docs/offline-all-plan.md, O2): pyosmium + shapely.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir osmium==4.0.2 shapely==2.0.6
WORKDIR /work
