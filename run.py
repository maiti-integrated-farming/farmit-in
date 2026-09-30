#!/usr/bin/env python3
"""FarmIt - Farm Management SaaS Platform"""
import os
from app import create_app

app = create_app(os.environ.get('FLASK_CONFIG') or 'development')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
