"""
Downloads the Olist Brazilian E-commerce dataset from Kaggle.
Saves temporarily to C:\Temp\olist (cleaned up when you want).
Loads all 9 tables into PostgreSQL — no permanent CSV files on your Desktop.

PREREQUISITES:
  1. .env must contain valid KAGGLE_USERNAME and KAGGLE_KEY
  2. sql\01_schema.sql must already be run (tables must exist)
"""
import os
import glob
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text
from src.db import engine
