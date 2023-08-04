import datetime
from pandas_market_calendars import get_calendar
from typing import Dict, Optional
from sqlite3 import IntegrityError
from bigbucks.model import Stock, User, WatchStock, Transaction
from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash, session
from datetime import datetime, date, time, timedelta
from pydantic import BaseModel, validator, ValidationError
from bigbucks import database
from flask_login import login_required, current_user
from yahooquery import Ticker
import requests
import pandas as pd
import yfinance as yf
import pprint as p
from pycoingecko import CoinGeckoAPI
import pytz


stocks_bp = Blueprint('stocks', __name__, template_folder='templates')

MAX_TRADING_SHARES = 1000000


# --- APIs --- #


# Used for validate if a stock exists
def ticker_exists(stock_symbol):
    ticker = Ticker(stock_symbol)
    info = ticker.summary_detail
    if "Quote not found" in info[stock_symbol] or "No fundamentals" in info[stock_symbol]:
        return False
    else:
        return True


# Used for get current market price when implementing real-time transaction
def get_market_price(stock_symbol):
    try:
        ticker = Ticker(stock_symbol)
        current_price = ticker.price[stock_symbol]["regularMarketPrice"]
        return round(float(current_price), 2)

    except Exception as e:
        print(str(e))
        return None


def get_historical_price(stock_symbol, query_time):
    crypto_symbols = ['BTC', 'ETH', 'LTC', 'XRP', 'BCH']

    if stock_symbol in crypto_symbols:
        return get_crypto_instaneous_price(stock_symbol, query_time)
    else:
        return get_instaneous_price(stock_symbol, query_time)


def get_crypto_instaneous_price(symbol, query_time):
    base_url = "https://www.alphavantage.co/query"
    api_key = current_app.config['ALPHA_VANTAGE_API_KEY']
    function = "DIGITAL_CURRENCY_DAILY"
    market = "USD"

    response = requests.get(base_url, params={
        "function": function,
        "symbol": symbol,
        "market": market,
        "apikey": api_key
    })

    if response.status_code != 200:
        raise Exception(
            "Failed to fetch historical price data with Alpha Vantage.")

    data = response.json()

    if "Time Series (Digital Currency Daily)" not in data:
        raise Exception("Invalid response from Alpha Vantage API.")

    time_series = data["Time Series (Digital Currency Daily)"]
    query_time_str = query_time.strftime("%Y-%m-%d")

    if query_time_str in time_series:
        unit_price = float(time_series[query_time_str]["4b. close (USD)"])
        return round(unit_price, 2)
    else:
        print(f"No data available for the given query_time: {query_time_str}")
        return None


# Used for get historical price when adding historical transaction
def get_instaneous_price(stock_symbol, query_time):
    slice_year, slice_month = get_alpha_slice(query_time)
    if not slice_year or not slice_month:
        unit_price = get_adjclose_price(stock_symbol, query_time)
        print(
            f"Due to the query time exceeding the capacity of Alpha Vantage, Yahoo Finance has been used to retrieve an adjusted closing price of {unit_price} for the requested date.")
    else:
        try:
            base_url = "https://www.alphavantage.co/query"
            api_key = current_app.config['ALPHA_VANTAGE_API_KEY']
            function = "TIME_SERIES_INTRADAY_EXTENDED"
            interval = "1min"
            response = requests.get(base_url, params={
                "function": function,
                "symbol": stock_symbol,
                "interval": interval,
                "slice": f"year{slice_year}month{slice_month}",
                "adjusted": "false",
                "apikey": api_key
            })

            if response.status_code != 200:
                raise Exception(
                    "Failed to fetch historical price data with Alpha Vantage.")

            lines = response.text.strip().split("\r\n")
            header = lines.pop(0).split(",")
            for line in lines:
                historical_data = dict(zip(header, line.split(",")))
                dt = datetime.strptime(
                    historical_data["time"], "%Y-%m-%d %H:%M:%S")
                if dt.date() == query_time.date() and dt.time() == query_time.time():
                    unit_price = round(float(historical_data["close"]), 2)

        except Exception as e:
            print(str(e))
            return None

    return unit_price


def get_alpha_slice(query_time):
    date_diff = (datetime.now() - query_time).days
    slice_number = (date_diff - 1) // 30 + 1
    if slice_number <= 12:
        slice_year = 1
    elif slice_number >= 24:
        return None, None
    else:
        slice_year = 2
    slice_month = slice_number if slice_number <= 12 else slice_number - 12
    return slice_year, slice_month


def get_adjclose_price(stock_symbol, query_time):
    start = query_time.date()
    print(start)
    end = start + timedelta(days=1)
    print(end)
    try:
        ticker = Ticker(stock_symbol)
        history_data = ticker.history(start=start, end=end).reset_index()
        if history_data.empty:
            print("No data available for the specified date range.")
            return None
        adjclose = round(float(history_data['adjclose'].iloc[0]), 2)
        return adjclose
    except Exception as e:
        print(str(e))
        return None


# --- APIs --- #


# --- Response Models for Trading --- #
def validate_trade_time(trade_time):
    query_date = trade_time.date()
    query_clock = trade_time.time()
    nyse_calendar = get_calendar('NYSE')
    schedule = nyse_calendar.schedule(
        start_date=query_date, end_date=query_date)
    if len(schedule) == 0:
        raise ValueError(f'No trading on {query_date}.')

    est = pytz.timezone('US/Eastern')
    market_open = schedule.iloc[0]['market_open'].to_pydatetime().astimezone(est).time()
    market_close = schedule.iloc[0]['market_close'].to_pydatetime().astimezone(est).time()
    if not (market_open <= query_clock <= market_close):
        raise ValueError(f'Not within stock trading hours.')

    if trade_time > datetime.now():
        raise ValueError(f'Trade time {trade_time} is in the future.')

    return trade_time


# A Basic model for parsing new transaction data from a form
class BaseTransactionModel(BaseModel):
    stock_symbol: str
    # Automatically attempt to cast number_of_shares to an integer. Would raise a ValidationError if failed.
    number_of_shares: int
    buy_or_sell: str

    @validator('buy_or_sell')
    def buy_or_sell_check(cls, value):
        if value not in ['buy', 'sell']:
            raise ValueError(
                'Invalid trade type. Please choose "buy" or "sell".')
        return value

    # Check if input stock symbol follows the correct format and exists,
    # and return the symbol in uppercase letters.
    @validator('stock_symbol')
    def stock_symbol_check(cls, value):
        if not value.isalpha() or len(value) > 5:
            raise ValueError('Stock symbol: 1-5 characters only.')
        stock_symbol = value.upper()
        if not ticker_exists(stock_symbol):
            raise ValueError('Stock symbol not found.')
        return stock_symbol

    #  Check if the input trade quantity is a positive integer within the maximum limit.
    @validator('number_of_shares')
    def number_of_shares_check(cls, value):
        if value <= 0:
            raise ValueError('Number of shares: positive integer only.')
        if value > MAX_TRADING_SHARES:
            raise ValueError(
                f'Number of shares cannot exceed {MAX_TRADING_SHARES}.')
        return value


# Child model for real-time transactions
class RealtimeTransactionModel(BaseTransactionModel):
    order_type: str
    limit_price: Optional[str]
    trade_time: datetime

    @validator('order_type')
    def buy_or_sell_check(cls, value):
        if value not in ['market', 'limit']:
            raise ValueError(
                'Invalid order type. Please choose "Market Order" or "Limit Order".')
        return value

    @validator('limit_price')
    def limit_price_check(cls, value, values):
        if value == '':
            value = None
        order_type = values.get('order_type')
        if order_type == 'limit':
            if value is None:
                raise ValueError('Limit price is required for limit orders')
            if float(value) < 0:
                raise ValueError('Limit price must be non-negative')
            # Considering whethere to set a boundary for the max value of limit price.
        else:
            if value is not None:
                raise ValueError(
                    'Limit price is only applicable for limit orders')
        return value

    # @validator('trade_time')
    # def trade_time_check(cls, value):
        # return validate_trade_time(value)


# Child model for historical transactions
class HistoricalTransactionModel(BaseTransactionModel):
    trade_time: datetime

    @validator('trade_time')
    def trade_time_check(cls, value):
        return validate_trade_time(value)


# --- Response Models for Trading --- #


# --- Helper Functions for Adding Transactions --- #
''' 
    To process a transaction, we have to:
    (1) Get latest data of account and portfolio, 
    (2) validate the transaction,
    (3) update the stocks table
'''


def process_transaction(transaction_data, unit_price):
    print("Start processing transaction...")
    current_holding = Stock.query.filter_by(
        user_id=current_user.id, stock_symbol=transaction_data.stock_symbol).first()
    user_data = User.query.filter_by(id=current_user.id).first()
    try:
        if validate_transaction(user_data, current_holding, transaction_data, unit_price):
            update_account_balance(user_data, transaction_data, unit_price)
            print("Successfully updated account balance.")
            create_new_transaction(transaction_data, unit_price)
            print("Successfuly created new transaction.")
            update_stock_position(
                current_holding, transaction_data, unit_price)
            print("Successfuly updated stock position.")
            database.session.commit()
            print("Trasaction processing DONE.")
            flash(
                f"Congratulations! You have successfully {transaction_data.buy_or_sell} {transaction_data.number_of_shares} shares of {transaction_data.stock_symbol}.",
                "success")
            return True
        else:
            print("Transaction not validated. Quit processing.")
            return False
    except Exception:
        database.session.rollback()
        return False


def validate_transaction(user_data, current_holding, transaction_data, unit_price):
    if transaction_data.buy_or_sell == 'buy':
        if user_data.account_balance < unit_price * transaction_data.number_of_shares:
            flash(
                "Sorry, your account doesn't have enough money for this transaction.", "error")
            return False
    elif transaction_data.buy_or_sell == 'sell':
        if not current_holding or current_holding.total_shares < transaction_data.number_of_shares:
            flash("Sorry, you don't have enough shares to sell at this point.", "error")
            return False

    return True


def update_account_balance(user_data, transaction_data, unit_price):
    if transaction_data.buy_or_sell == 'buy':
        user_data.account_balance -= unit_price * transaction_data.number_of_shares
    else:
        user_data.account_balance += unit_price * transaction_data.number_of_shares

    database.session.flush()


def create_new_transaction(transaction_data, unit_price):
    try:
        order_type = getattr(transaction_data, 'order_type', None)
        trade_time = getattr(transaction_data, 'trade_time', None)
        new_transaction = Transaction(transaction_data.stock_symbol,
                                      unit_price,
                                      transaction_data.number_of_shares,
                                      transaction_data.buy_or_sell,
                                      current_user.id,
                                      order_type,
                                      trade_time
                                      )
        database.session.add(new_transaction)
        database.session.flush()

    except Exception as e:
        print(str(e))


def update_stock_position(current_holding, transaction_data, unit_price):
    try:
        if current_holding:
            if transaction_data.buy_or_sell == 'buy':
                updated_cumulative_buy = current_holding.cumulative_buy + \
                    transaction_data.number_of_shares
                updated_average_buy_price = (current_holding.cumulative_buy * current_holding.average_buy_price +
                                             transaction_data.number_of_shares * unit_price) / updated_cumulative_buy
                current_holding.cumulative_buy = updated_cumulative_buy
                current_holding.average_buy_price = updated_average_buy_price

            else:
                updated_cumulative_sell = current_holding.cumulative_sell + \
                    transaction_data.number_of_shares
                updated_average_sell_price = (current_holding.cumulative_sell * current_holding.average_sell_price +
                                              transaction_data.number_of_shares * unit_price) / updated_cumulative_sell
                current_holding.cumulative_sell = updated_cumulative_sell
                current_holding.average_sell_price = updated_average_sell_price
                if current_holding.total_shares - transaction_data.number_of_shares == 0:
                    database.session.delete(current_holding)

            current_holding.latest_trade_time = transaction_data.trade_time

        else:
            new_stock = Stock(
                stock_symbol=transaction_data.stock_symbol,
                cumulative_buy=transaction_data.number_of_shares,
                cumulative_sell=0,
                average_buy_price=unit_price,
                average_sell_price=0,
                latest_trade_time=transaction_data.trade_time,
                user_id=current_user.id
            )
            database.session.add(new_stock)

        database.session.flush()

    except Exception as e:
        print(str(e))


# --- Helper Functions for Adding Transactions --- #


# --- Trading --- #
@login_required
@stocks_bp.route('/trade_stock', methods=['GET', 'POST'])
def trade_stock():
    if request.method == 'POST':
        form_id = request.form['form_id']
        print(f"{form_id} requested")

        try:
            if form_id == 'form1':
                # validate_trade_time(datetime.now())
                transaction_data = RealtimeTransactionModel(
                    stock_symbol=request.form['stock_symbol'],
                    number_of_shares=request.form['number_of_shares'],
                    buy_or_sell=request.form['buy_or_sell'],
                    order_type=request.form['order_type'],
                    limit_price=request.form['limit_price'],
                    trade_time=datetime.now()
                )

                if transaction_data.order_type == 'limit':
                    flash(
                        "Sorry, the feature of limit order is still under development. Please try market order. We appreciate your patience.",
                        "error")
                    return redirect(url_for('stocks.trade_stock'))

                unit_price = get_market_price(transaction_data.stock_symbol)
                print(f"Current market price retrieved: {unit_price}")

            else:
                transaction_data = HistoricalTransactionModel(
                    stock_symbol=request.form['stock_symbol'],
                    number_of_shares=request.form['number_of_shares'],
                    buy_or_sell=request.form['buy_or_sell'],
                    trade_time=request.form['trade_time']
                )
                unit_price = get_historical_price(
                    transaction_data.stock_symbol, transaction_data.trade_time)
                print(f"Historical market price retrieved: {unit_price}")

            if unit_price is not None and process_transaction(transaction_data, unit_price):
                return redirect(url_for('stocks.portfolio'))
            else:
                return redirect(url_for('stocks.trade_stock'))

        except ValidationError as e:
            for error in e.errors():
                flash(error['msg'])
            return redirect(url_for('stocks.trade_stock'))

        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('stocks.trade_stock'))

        except Exception as e:
            flash(f"An unexpected error occurred: {str(e)}", 'error')
            return redirect(url_for('stocks.trade_stock'))

    return render_template('trade_stock.html')


# --- Trading --- #


# --- Transaction History --- #
@stocks_bp.route('/transaction_history', methods=['GET'])
@login_required
def transaction_history():
    user_transactions = Transaction.query.filter_by(
        user_id=current_user.id).order_by(Transaction.trade_time.desc()).all()
    transaction_data = []

    if len(user_transactions) != 0:
        for transaction in user_transactions:
            crypto_symbols = ['BTC', 'ETH', 'LTC', 'XRP', 'BCH']

            if transaction.stock_symbol in crypto_symbols:
                company_name = get_crypto_full_name(transaction.stock_symbol)

            else:
                ticker_symbol = transaction.stock_symbol
                ticker = Ticker(ticker_symbol)
                ticker_price = ticker.price
                company_name = ticker_price[ticker_symbol]["longName"]

            if transaction.buy_or_sell == 'buy':
                transaction_amount = "+" + \
                                     str(round(transaction.amount, 2))
            else:
                transaction_amount = "-" + \
                                     str(round(transaction.amount, 2))

            transaction_data.append({
                'symbol': transaction.stock_symbol,
                'company': company_name,
                'shares': transaction.number_of_shares,
                'unit_price': transaction.unit_price,
                'amount': transaction_amount,
                'buy_or_sell': transaction.buy_or_sell.upper(),
                'order_type': transaction.order_type.upper(),
                'time': transaction.trade_time.strftime("%Y-%m-%d %H:%M")
            })

    return render_template('transaction_history.html', transaction_data=transaction_data)


def get_crypto_full_name(symbol):
    cg = CoinGeckoAPI()
    search_result = cg.search(symbol)
    if search_result and search_result['coins']:
        return search_result['coins'][0]['name']
    return None


# --- Transaction History --- #


# --- Portfolio --- #
def calculate_summary_data(stocks):
    total_asset = 0
    total_earnings = 0
    total_return_percentage = 0
    total_principle = 0

    for stock in stocks:
        current_price = get_market_price(stock.stock_symbol)
        total_asset += current_price * stock.total_shares
        total_principle += stock.principle

    total_earnings = total_asset - total_principle
    total_return_percentage = (total_earnings / total_principle) * 100
    summary_data = {
        'total_asset': round(total_asset, 2),
        'total_earnings': round(total_earnings, 2),
        'total_return': round(total_return_percentage, 2)
    }

    return summary_data


@stocks_bp.route('/portfolio', methods=['GET', 'POST'])
@login_required
def portfolio():
    user_stocks = Stock.query.filter_by(user_id=current_user.id).all()
    stock_data = []
    summary_data = {}

    if len(user_stocks) != 0:
        summary_data = calculate_summary_data(user_stocks)

        for stock in user_stocks:
            crypto_symbols = ['BTC', 'ETH', 'LTC', 'XRP', 'BCH']

            if stock.stock_symbol in crypto_symbols:
                company_name = get_crypto_full_name(stock.stock_symbol)

            else:
                ticker_symbol = stock.stock_symbol
                ticker = Ticker(ticker_symbol)
                ticker_price = ticker.price
                company_name = ticker_price[ticker_symbol]["longName"]

            current_price = ticker.price[ticker_symbol]["regularMarketPrice"]
            stock_data.append({
                'symbol': stock.stock_symbol,
                'company': company_name,
                'average_purchase_price': round(stock.average_buy_price, 2),
                'current_price': current_price,
                'shares': stock.total_shares,
                'latest_trade_time': stock.latest_trade_time.strftime("%Y-%m-%d")
            })

    return render_template('portfolio.html', stock_data=stock_data, summary=summary_data)


# --- Portfolio --- #


# --- Stock Price Change Chart --- #
def get_date_price(symbol, start_date, end_date):
    ticker = Ticker(symbol)
    history_data = ticker.history(start=start_date, end=end_date)
    history_data = history_data.reset_index()

    if history_data.empty:
        flash('No available data within the requested date range.', 'error')
        return [], []

    adjclose_list = history_data['adjclose'].tolist()
    date = history_data['date']
    date = pd.to_datetime(date)
    date_list = date.dt.strftime('%Y-%m-%d').tolist()

    return date_list, adjclose_list


@stocks_bp.route('/detail/<symbol>', methods=['GET', 'POST'])
@login_required
def detail(symbol):
    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        session['start_date'] = start_date
        session['end_date'] = end_date
        date, adjclose = get_date_price(symbol, start_date, end_date)

        return redirect(url_for('stocks.detail', symbol=symbol))

    elif 'start_date' in session and 'end_date' in session:
        start_date = session['start_date']
        end_date = session['end_date']
        date, adjclose = get_date_price(symbol, start_date, end_date)
        session.pop('start_date', None)
        session.pop('end_date', None)

    else:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=14)
        date, adjclose = get_date_price(symbol, start_date, end_date)

    return render_template("stock_chart.html", symbol=symbol, date=date, adjclose=adjclose)


# --- Stock Price Change Chart --- #


# --- Watchlist --- #

@login_required
@stocks_bp.route('/watchlist/')
def watchlist():
    stock = WatchStock.query.order_by(WatchStock.id).filter_by(
        user_id=current_user.id).all()
    stock_data = []
    for stock in stock:
        ticker_symbol = stock.stock_symbol
        ticker = Ticker(ticker_symbol)
        ticker_price = ticker.price
        company_name = ticker_price[ticker_symbol]["longName"]
        current_price = ticker.price[ticker_symbol]["regularMarketPrice"]

        stock_data.append({
            'symbol': ticker_symbol,
            'company': company_name,
            'current_price': current_price,
            'id': stock.id
        })
    return render_template('watchlist.html', stock_data=stock_data)


@login_required
@stocks_bp.route('/add_stock_to_watchlist', methods=["POST"])
def add_stock_to_watchlist():
    new_watch_stock = WatchStock(
        stock_symbol=request.form['stockSymbol'].upper(), user_id=current_user.id)
    if ticker_exists(new_watch_stock.stock_symbol):
        database.session.add(new_watch_stock)
        try:
            database.session.commit()
            flash(
                f'New stock added to watchlist: {new_watch_stock.stock_symbol}!')
        except IntegrityError:
            database.session.rollback()
            flash(
                f'Stock {new_watch_stock.stock_symbol} is already in your watchlist.', 'error')
    else:
        flash(f'{new_watch_stock.stock_symbol} is not a valid Ticker symbol.', 'error')

    return redirect(url_for('stocks.watchlist'))


@login_required
@stocks_bp.route('/remove_watch_item', methods=["POST"])
def remove_watch_item():
    stock = WatchStock.query.get(request.form["stock.id"])
    database.session.delete(stock)
    database.session.commit()
    return redirect(url_for('stocks.watchlist'))


# --- Watchlist --- #
