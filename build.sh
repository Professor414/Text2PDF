#!/usr/bin/env bash
# exit on error
set -o errexit

# 1. ដំឡើង Python libraries ពី requirements.txt
pip install -r requirements.txt

# 2. ដំឡើង Dependencies របស់ WeasyPrint និង Font ខ្មែរ
# នេះជាផ្នែកដែលដោះស្រាយបញ្ហា Font!
apt-get update && apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libcairo2 fonts-khmeros
