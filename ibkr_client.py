import os
from dotenv import load_dotenv
from ib_insync import *
import time
import yfinance as yf
import pandas as pd

load_dotenv()


class IbClient:
    def __init__(self):
        self.ib = IB()
        self.ib.connect("127.0.0.1", 4002, clientId=1)
        self.df = pd.read_csv("S&P500.csv")

        print("api Connceted!")

    def get_stocks(self):
        self.tickers = self.df["Symbol"].tolist()
        return self.tickers

    def disconnect_ibkr(self):
        time.sleep(2)
        self.ib.disconnect()
        print("api Disconnected!")
