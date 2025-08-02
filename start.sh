#!/bin/bash
# For production use with gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app