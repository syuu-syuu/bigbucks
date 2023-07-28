from bigbucks import database
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import event, text
from sqlalchemy.ext.hybrid import hybrid_property


INITIAL_BALANCE = 1000000


class Transaction(database.Model):
    __tablename__ = 'transactions'

    id = database.Column(database.Integer, primary_key=True)
    stock_symbol = database.Column(database.String(5), nullable=False)
    unit_price = database.Column(database.Float, nullable=False)
    number_of_shares = database.Column(database.Integer, nullable=False)
    amount = database.Column(database.Float, nullable=False)
    buy_or_sell = database. Column(
        database.String(4), nullable=False)
    order_type = database. Column(database.String(
        6), nullable=False)
    trade_time = database.Column(database.DateTime, nullable=False)
    user_id = database.Column(
        database.Integer, database.ForeignKey('users.id', name='transactions_users_fk'))

    def __init__(self, stock_symbol: str, unit_price: float, number_of_shares: int, buy_or_sell: str, user_id: int, order_type: str = None, trade_time: datetime = None):
        self.stock_symbol = stock_symbol
        self.unit_price = unit_price
        self.number_of_shares = number_of_shares
        self.amount = unit_price * number_of_shares
        self.buy_or_sell = buy_or_sell
        self.order_type = order_type if order_type is not None else "market"
        self.trade_time = trade_time if trade_time is not None else datetime.now()
        self.user_id = user_id


class Stock(database.Model):
    __tablename__ = 'stocks'

    id = database.Column(database.Integer, primary_key=True)
    stock_symbol = database.Column(database.String(5), nullable=False)
    cumulative_buy = database.Column(database.Integer, nullable=False)
    cumulative_sell = database.Column(database.Integer, nullable=False)
    average_buy_price = database.Column(database.Float, nullable=False)
    average_sell_price = database.Column(database.Float, nullable=False)
    latest_trade_time = database.Column(database.DateTime, nullable=False)
    user_id = database.Column(database.Integer, database.ForeignKey(
        'users.id', name='stock_user_fk'))

    def __init__(self, stock_symbol: str, cumulative_buy: int, cumulative_sell: int, average_buy_price: float, average_sell_price: float, latest_trade_time: datetime, user_id: int):
        self.stock_symbol = stock_symbol

        self.cumulative_buy = cumulative_buy
        self.cumulative_sell = cumulative_sell

        self.average_buy_price = average_buy_price
        self.average_sell_price = average_sell_price

        self.latest_trade_time = latest_trade_time
        self.user_id = user_id

    @hybrid_property
    def total_shares(self):
        return self.cumulative_buy - self.cumulative_sell

    @hybrid_property
    def principle(self):
        return self.average_buy_price * self.cumulative_buy - self.average_sell_price * self.cumulative_sell


class User(database.Model):
    __tablename__ = 'users'

    id = database.Column(database.Integer, primary_key=True)
    username = database.Column(database.String)
    email = database.Column(database.String, unique=True)
    password_hashed = database.Column(database.String(128), nullable=False)
    registered_on = database.Column(database.DateTime, nullable=False)
    account_balance = database.Column(
        database.Float, nullable=False, default=INITIAL_BALANCE)
    stocks = database.relationship('Stock', backref='user')
    is_admin = database.Column(database.Boolean, nullable=False, default=False)

    def __init__(self, username: str, email: str, password_plaintext: str):
        self.username = username
        self.email = email
        self.password_hashed = self._generate_password_hash(password_plaintext)
        self.registered_on = datetime.now()

    def is_password_correct(self, password_plaintext: str):
        return check_password_hash(self.password_hashed, password_plaintext)

    @staticmethod
    def _generate_password_hash(password_plaintext):
        return generate_password_hash(password_plaintext)

    def __repr__(self):
        return f'<User: {self.email}>'

    @property
    def is_authenticated(self):
        """Return True if the user has been successfully registered."""
        return True

    @property
    def is_active(self):
        """Always True, as all users are active."""
        return True

    @property
    def is_anonymous(self):
        """Always False, as anonymous users aren't supported."""
        return False

    def get_id(self):
        """Return the user ID as a unicode string (`str`)."""
        return str(self.id)


@staticmethod
def set_admin_user(mapper, connection, target):

    if target.email == "mpoz425@gmail.com":
        query = text(
            "UPDATE users SET is_admin = :is_admin WHERE email = :email")
        connection.execute(
            query,
            {"is_admin": True, "email": target.email})


event.listen(User, "after_insert", set_admin_user)


@staticmethod
def set_admin_user(mapper, connection, target):

    if target.email == "mpoz425@gmail.com":
        query = text(
            "UPDATE users SET is_admin = :is_admin WHERE email = :email")
        connection.execute(
            query,
            {"is_admin": True, "email": target.email})


event.listen(User, "after_insert", set_admin_user)


class WatchStock(database.Model):
    __tablename__ = 'watchstocks'

    id = database.Column(database.Integer, primary_key=True)
    stock_symbol = database.Column(
        database.String, nullable=False)
    user_id = database.Column(
        database.Integer, database.ForeignKey('users.id', name='watch_stock_user_id_fk'))

    def __init__(self, stock_symbol: str, user_id: int):
        self.stock_symbol = stock_symbol
        self.user_id = user_id

class FiveYearHoldings(database.Model):
    "Database table which contains 5 years of of all stocks held by users."

    __tablename__ = "FiveYearHoldings"

    id = database.Column(database.Integer, primary_key=True)
    date = database.Column(database.Date, nullable=False)
    open = database.Column(database.Float, nullable=False)
    high = database.Column(database.Float, nullable=False)
    low = database.Column(database.Float, nullable=False)
    close = database.Column(database.Float, nullable=False)
    volume = database.Column(database.Integer, nullable=False)

    def __init__(self, date, open, high, low, close, volume):
        self.date = date
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume

    def __repr__(self):
        return f'<StockData {self.date} {self.close}>'
