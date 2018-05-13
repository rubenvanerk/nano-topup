import gdax
import os
import yaml
from bs4 import BeautifulSoup
import requests
import json
import time
from binance.client import Client

base_dir = os.path.dirname(os.path.realpath(__file__))

with open(base_dir + os.sep + "config.yaml") as ymlfile:
    cfg = yaml.load(ymlfile)

GDAX_ORDER_DONE_STATUS = "done"

gdax_api_key = os.environ["GDAX_API_KEY"]
gdax_api_secret = os.environ["GDAX_API_SECRET"]
gdax_api_pass_phrase = os.environ["GDAX_PASSPHRASE"]

binance_api_key = os.environ["BINANCE_API_KEY"]
binance_api_secret = os.environ["BINANCE_API_SECRET"]

gdax_client = gdax.AuthenticatedClient(gdax_api_key, gdax_api_secret, gdax_api_pass_phrase)

binance_client = Client(binance_api_key, binance_api_secret)


# check nano balance
def get_nano_balance(address):
    nano_explorer = "https://nano.org/en/explore/account/" + address
    content = requests.get(nano_explorer).content
    soup = BeautifulSoup(content, "html.parser")
    balance = soup.h1.string
    if balance.endswith('XRB'):
        balance = balance[:-3]
    balance.strip()
    return float(balance)


def nano_to_eur(balance):
    coinmarketcap = requests.get("https://api.coinmarketcap.com/v1/ticker/nano/?convert=EUR").content
    coinmarketcap = json.loads(coinmarketcap)
    eur_value = float(coinmarketcap[0]["price_eur"])
    return balance * eur_value


# ETH kopen (gdax)
def buy_bitcoin(funds):
    order = gdax_client.buy(type='market',
                            funds=funds,
                            product_id='ETH-EUR')

    while not order["status"] == GDAX_ORDER_DONE_STATUS:
        order = gdax_client.get_order(order["id"])
        time.sleep(5)

    return float(order["filled_size"])


# get binance ETH deposit address (binance)
def get_deposit_address():
    success = False
    address = ""
    while not success:
        response = binance_client.get_deposit_address(asset='ETH')
        success = response["success"]
        if success:
            address = response["address"]
        else:
            time.sleep(1)
    return address


# ETH withdrawen naar binance (gdax)
def withdraw_eth(address, amount):
    return gdax_client.crypto_withdraw(amount, "ETH", address)


def get_nano_price():
    return float(binance_client.get_ticker(symbol="NANOETH")["lastPrice"])


def get_binance_balance():
    return float(binance_client.get_asset_balance(asset="ETH")["free"])


# Nano kopen met ETH (binance)
def buy_nano(eth_amount, nano_price):
    nano_amount = float(format(eth_amount / (nano_price * 1.01), '.2f'))
    return binance_client.create_order(
        symbol='NANOETH',
        side=Client.SIDE_BUY,
        type=Client.ORDER_TYPE_MARKET,
        quantity=nano_amount
    )


# Nano withdrawen naar wallet (binance)
def withdraw_nano(nano_amount):
    return binance_client.withdraw(
        asset="NANO",
        address=cfg["nano"]["address"],
        amount=nano_amount
    )


def start_process():
    current_balance = get_nano_balance(cfg["nano"]["address"])
    print("Current balance = " + str(current_balance))
    current_balance_in_eur = nano_to_eur(current_balance)
    print("Current balance in eur = " + str(current_balance_in_eur))
    buying_in_progress = cfg["BUYING_IN_PROGRESS"]
    if current_balance_in_eur < float(cfg["nano"]["threshold"]) and buying_in_progress is not "1":
        print("START YOUR ENGINES, HERE WE GO")
        cfg["BUYING_IN_PROGRESS"] = "1"

        with open(base_dir + os.sep + "config.yaml", "w") as f:
            yaml.dump(cfg, f)

        eth_amount = buy_bitcoin(cfg["nano"]["buy_amount"])
        print("Amount eth bought = " + str(eth_amount))
        eth_address = get_deposit_address()
        print("eth address to withdraw to = " + str(eth_address))
        print(withdraw_eth(eth_address, eth_amount))
        print("eth withdrawn from gdax to binance")
        while get_binance_balance() < eth_amount:
            print("Waiting for eth to arrive at Binance")
            time.sleep(60)
        print("eth arrived at binance")

        nano_price = get_nano_price()
        print("Current nano price" + str(nano_price))
        transaction = buy_nano(eth_amount, nano_price)
        print(transaction)
        nano_amount = transaction['executedQty']
        print("Amount of nano bought = " + str(nano_amount))

        print(withdraw_nano(nano_amount))
        print("Nano withdrawn to " + cfg["nano"]["address"])
        time.sleep(600)
        os.environ["BUYING_IN_PROGRESS"] = "0"
        with open(base_dir + os.sep + "config.yaml", "w") as f:
            yaml.dump(cfg, f)


start_process()
