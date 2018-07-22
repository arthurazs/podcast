#!/bin/bash

export FLASK_APP=tst.py
export FLASK_DEBUG=1
source ~/apps/venv/python3/bin/activate
clear; clear; python -V
flask run
