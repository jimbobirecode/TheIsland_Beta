#!/usr/bin/env python3
"""
Entry point for Golf Club Email Bot
This file imports the Flask app for Gunicorn
"""

from island_email_bot import app

if __name__ == '__main__':
    import os
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
