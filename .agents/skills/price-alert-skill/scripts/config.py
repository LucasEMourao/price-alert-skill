#!/usr/bin/env python3

"""Configuration for affiliate link generation and marketplace settings."""

import os

AMAZON_AFFILIATE_TAG = os.environ.get("AMAZON_AFFILIATE_TAG", "brunoentende-20")

ML_MATT_WORD = os.environ.get("ML_MATT_WORD", "tb20240811145500")
ML_MATT_TOOL = os.environ.get("ML_MATT_TOOL", "21915026")