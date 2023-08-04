import yfinance as yf
from flask import Blueprint, render_template
from bigbucks.model import Stock
from bigbucks import database
from flask_login import login_required, current_user
from yahooquery import Ticker
from ..stocks import calculate_summary_data


home_bp = Blueprint(
    'home', __name__, template_folder='templates')


@home_bp.route('/')
def index():
    summary_data = None
    if current_user.is_authenticated:
        user_stocks = Stock.query.filter_by(user_id=current_user.id).all()
        if len(user_stocks) != 0:
            summary_data = calculate_summary_data(user_stocks)

        return render_template('index.html', summary=summary_data)

    return render_template('index.html')


@home_bp.route('/about')
def about():
    return render_template('about.html')

@home_bp.route('/other')
def other():
    return render_template('other.html')
